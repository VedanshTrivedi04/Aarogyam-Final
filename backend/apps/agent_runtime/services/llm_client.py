"""
Groq LLM Client
================
Thin wrapper around the Groq SDK for the Agent Runtime's reasoning layer.
Follows the same "never raise" contract as apps.ai_engine.services.risk_engine
— callers always get a structured result, even when Groq is down, slow, or
misconfigured. Reuses the same circuit-breaker pattern as
apps.ai_engine.services.inference.InferenceService so repeated Groq failures
temporarily stop new LLM calls instead of retrying into a dead API forever.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger("medadhere.agent_runtime.llm")


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class LLMResult:
    success: bool
    content: str = ""
    tool_calls: list = field(default_factory=list)
    error: Optional[str] = None


class LLMClient:
    """Never raises — every method returns an LLMResult."""

    _client = None
    _circuit_breaker = None

    @classmethod
    def _get_circuit_breaker(cls):
        if cls._circuit_breaker is None:
            from apps.ai_engine.services.inference import CircuitBreaker
            cls._circuit_breaker = CircuitBreaker(
                "groq_llm", failure_threshold=5, recovery_timeout=120
            )
        return cls._circuit_breaker

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            from groq import Groq
            if not settings.GROQ_API_KEY:
                raise RuntimeError("GROQ_API_KEY is not configured")
            cls._client = Groq(api_key=settings.GROQ_API_KEY)
        return cls._client

    @classmethod
    def reason_with_tools(
        cls,
        system_prompt: str,
        user_prompt: str,
        tools: list,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResult:
        """
        Single-turn reasoning call: gives the LLM a system prompt describing
        its role + the tools it may call (OpenAI/Groq tool-calling schema),
        plus a user prompt containing the gathered patient context. Returns
        whichever tool call(s) the LLM decided to make and/or its free-text
        reasoning.
        """
        breaker = cls._get_circuit_breaker()
        if not breaker.is_available():
            logger.warning("Groq circuit breaker OPEN — skipping LLM call")
            return LLMResult(success=False, error="circuit_open")

        try:
            client = cls._get_client()
            response = client.chat.completions.create(
                model=model or settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=20,
            )
            breaker.record_success()

            message = response.choices[0].message
            tool_calls = []
            for tc in (message.tool_calls or []):
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(ToolCall(name=tc.function.name, arguments=args))

            return LLMResult(success=True, content=message.content or "", tool_calls=tool_calls)

        except Exception as e:
            logger.error(f"Groq LLM call failed: {e}")
            breaker.record_failure()
            return LLMResult(success=False, error=str(e))
