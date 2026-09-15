"""
Inference Pipeline
==================
Real-time and batch inference for adherence risk scoring.

Key design principles:
  1. ALWAYS returns a result — never raises to callers
  2. Circuit breaker: if model fails N times → auto-switch to fallback
  3. SHAP values for explainability on every prediction
  4. Sub-200ms target latency (model cached in memory)
  5. Results stored in DB asynchronously

Circuit breaker states: CLOSED (normal) → OPEN (fallback) → HALF-OPEN (testing recovery)
"""

import logging
import threading
import time as time_module
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Dict, List, Optional

logger = logging.getLogger("medadhere.ai_engine.inference")


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """
    Simple circuit breaker for ML inference.
    CLOSED → normal
    OPEN → use fallback (triggered after failure_threshold failures)
    HALF-OPEN → try one real inference to see if model recovered
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN:
                if time_module.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    logger.info(f"Circuit {self.name}: OPEN → HALF_OPEN (testing recovery)")
        return self._state

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            if self._state == self.HALF_OPEN:
                self._state = self.CLOSED
                logger.info(f"Circuit {self.name}: HALF_OPEN → CLOSED (model recovered)")

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time_module.time()
            if self._failure_count >= self.failure_threshold:
                if self._state != self.OPEN:
                    self._state = self.OPEN
                    logger.error(
                        f"Circuit {self.name}: CLOSED → OPEN "
                        f"(after {self._failure_count} failures — using fallback)"
                    )

    def is_available(self) -> bool:
        return self.state in (self.CLOSED, self.HALF_OPEN)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class RiskScoreResult:
    patient_id: str
    risk_score: float
    risk_level: str
    confidence: float
    reasons: List[str]
    source: str  # "ML_MODEL" | "RULE_BASED_FALLBACK" | "RULE_BASED_FALLBACK_ERROR"
    is_advisory_only: bool = True
    model_version: Optional[str] = None
    feature_snapshot: Dict = field(default_factory=dict)
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "source": self.source,
            "is_advisory_only": True,
            "model_version": self.model_version,
            "computed_at": self.computed_at,
        }


# ---------------------------------------------------------------------------
# Inference Service
# ---------------------------------------------------------------------------


class InferenceService:
    """
    Singleton inference service.
    Holds the loaded model in memory for fast repeated inference.
    All public methods are safe — they never raise to callers.
    """

    _instance: Optional["InferenceService"] = None
    _lock = threading.Lock()
    _circuit_breaker = CircuitBreaker("ml_inference", failure_threshold=5, recovery_timeout=120)
    _model_payload: Optional[dict] = None
    _model_version: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "InferenceService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def warmup(cls):
        """Pre-load model into memory. Called at Django startup."""
        try:
            instance = cls.get_instance()
            instance._ensure_model_loaded()
            logger.info(f"AI Engine warmed up with model v{cls._model_version}")
        except Exception as e:
            logger.warning(f"AI warmup failed (fallback will be used): {e}")

    def _ensure_model_loaded(self):
        """Lazy model loading — thread-safe."""
        if self._model_payload is not None:
            return

        with self._lock:
            if self._model_payload is not None:
                return
            try:
                from apps.ai_engine.services.training import load_model
                self._model_payload = load_model()
                InferenceService._model_version = self._model_payload.get("config", {}).get(
                    "model_version", "unknown"
                )
                logger.info(f"Model loaded into memory: v{self._model_version}")
            except Exception as e:
                logger.warning(f"Model load failed: {e}")
                raise

    def _ml_predict(self, feature_vector) -> RiskScoreResult:
        """Run XGBoost inference with SHAP explanations."""
        import numpy as np

        self._ensure_model_loaded()
        model = self._model_payload["model"]
        feature_names = self._model_payload["feature_names"]

        # Build input array in correct feature order
        features_dict = feature_vector.features
        X = np.array([[features_dict.get(f, 0) for f in feature_names]])

        # Predict probability of non-adherence
        prob = float(model.predict_proba(X)[0][1])
        prob = self._apply_safety_calibration(prob, features_dict)

        # Risk level
        if prob >= 0.75:
            risk_level = "critical"
        elif prob >= 0.55:
            risk_level = "high"
        elif prob >= 0.30:
            risk_level = "medium"
        else:
            risk_level = "low"

        # SHAP values for top-3 explanations
        reasons = self._compute_shap_reasons(model, X, feature_names)

        return RiskScoreResult(
            patient_id=feature_vector.patient_id,
            risk_score=round(prob, 4),
            risk_level=risk_level,
            confidence=min(0.95, 0.60 + feature_vector.data_quality_score * 0.35),
            reasons=reasons,
            source="ML_MODEL",
            model_version=self._model_version,
            feature_snapshot={k: features_dict.get(k) for k in feature_names},
        )

    @staticmethod
    def _apply_safety_calibration(prob: float, features: Dict) -> float:
        """
        Guardrail for extremes the model has essentially no training
        examples for. A patient with literally zero missed doses across a
        long history is statistically near-impossible to generate in any
        finite synthetic training set (even a 96%-base-adherence archetype
        has under a 0.1% chance of zero misses across ~180 doses), so the
        model has to extrapolate there and can land on a mediocre score for
        an objectively excellent record. This only engages for unambiguous
        extremes with enough observed history to trust — it never overrides
        the model in the ambiguous middle of the range.
        """
        missed_30d = features.get("missed_count_30d", 0)
        adherence_30d = features.get("adherence_rate_30d", 1.0)
        adherence_90d = features.get("adherence_rate_90d", 1.0)
        streak = features.get("current_streak_days", 0)
        missed_7d = features.get("missed_count_7d", 0)
        adherence_7d = features.get("adherence_rate_7d", 1.0)

        if missed_30d == 0 and adherence_30d >= 0.98 and adherence_90d >= 0.98 and streak >= 14:
            return min(prob, 0.20)
        if missed_7d >= 5 and adherence_7d < 0.30:
            return max(prob, 0.80)
        return prob

    def _compute_shap_reasons(
        self, model, X: "np.ndarray", feature_names: List[str]
    ) -> List[str]:
        """
        Generate human-readable SHAP explanations.
        Falls back to feature importance if SHAP unavailable.
        """
        try:
            import shap
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X)
            values = shap_values[0]

            # Top 3 features by absolute SHAP value
            ranked = sorted(
                zip(feature_names, values), key=lambda x: abs(x[1]), reverse=True
            )[:3]

            return [_feature_to_reason(name, val) for name, val in ranked if abs(val) > 0.005]

        except Exception:
            # Fallback: use feature importance from model
            try:
                importances = model.feature_importances_
                ranked = sorted(
                    zip(feature_names, importances), key=lambda x: x[1], reverse=True
                )[:3]
                return [f"Key factor: {name.replace('_', ' ')}" for name, _ in ranked]
            except Exception:
                return ["Risk assessment based on adherence history"]

    def predict(
        self,
        patient_id: str,
        events_df,
        prescriptions_data: Optional[List[Dict]] = None,
        patient_data: Optional[Dict] = None,
        app_opens_7d: int = 7,
        refill_days_late: int = 0,
        as_of: Optional[datetime] = None,
    ) -> RiskScoreResult:
        """
        Main public inference method.
        Always returns a RiskScoreResult — never raises.

        Flow:
          0. If patient has no usable dose history → baseline result (the
             model was never trained on an all-defaults input and
             extrapolates poorly)
          1. Build feature vector
          2. If circuit open → fallback immediately
          3. Try ML prediction
          4. On failure → circuit failure + fallback
          5. Persist result asynchronously
        """
        try:
            from apps.ai_engine.services.feature_engineering import build_feature_vector
            fv = build_feature_vector(
                patient_id=patient_id,
                events_df=events_df,
                prescriptions_data=prescriptions_data,
                patient_data=patient_data,
                app_opens_7d=app_opens_7d,
                refill_days_late=refill_days_late,
                as_of=as_of,
            )
        except Exception as e:
            logger.error(f"Feature engineering failed for {patient_id}: {e}")
            fv = None

        # If feature engineering failed, use minimal fallback
        if fv is None:
            return self._use_fallback(patient_id, {})

        # No usable historical events (brand-new patient, or every scheduled
        # dose is still in the future) → neutral baseline, not an ML guess.
        if fv.data_quality_score <= 0:
            return self._baseline_new_patient(patient_id)

        # Circuit breaker check
        if not self._circuit_breaker.is_available():
            logger.info(f"Circuit OPEN — using fallback for {patient_id}")
            return self._use_fallback(patient_id, fv.features)

        # Attempt ML inference
        try:
            result = self._ml_predict(fv)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            logger.error(f"ML inference failed for {patient_id}: {e}")
            self._circuit_breaker.record_failure()
            return self._use_fallback(patient_id, fv.features)

    def _baseline_new_patient(self, patient_id: str) -> RiskScoreResult:
        """
        Brand-new patients with no dose history at all get a low, neutral
        baseline instead of an ML prediction — the model has never seen an
        all-defaults ("perfect" but data-free) input and extrapolates badly.
        """
        return RiskScoreResult(
            patient_id=patient_id,
            risk_score=0.12,
            risk_level="low",
            confidence=0.30,
            reasons=["Baseline / New Patient — No dose history recorded yet"],
            source="BASELINE_NEW_PATIENT",
            model_version=None,
        )

    def _use_fallback(self, patient_id: str, features: Dict) -> RiskScoreResult:
        """Delegate to rule-based fallback and wrap result."""
        from apps.ai_engine.services.fallback import assess_risk, FallbackRiskResult

        fb_result = assess_risk(patient_id=patient_id, features=features)

        return RiskScoreResult(
            patient_id=fb_result.patient_id,
            risk_score=fb_result.risk_score,
            risk_level=fb_result.risk_level,
            confidence=fb_result.confidence,
            reasons=fb_result.reasons,
            source=fb_result.source,
            model_version=None,
        )


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def _feature_to_reason(feature_name: str, shap_value: float) -> str:
    """Convert feature name + SHAP value to human-readable explanation."""
    direction = "increasing" if shap_value > 0 else "reducing"

    messages = {
        "adherence_rate_7d": f"7-day adherence rate is {direction} risk",
        "missed_count_7d": f"Recent missed doses are {direction} risk",
        "consecutive_miss_streak": f"Consecutive misses are {direction} risk",
        "adherence_rate_30d": f"30-day adherence history is {direction} risk",
        "doses_per_day": f"Medication complexity is {direction} risk",
        "weekend_miss_ratio": f"Weekend adherence pattern is {direction} risk",
        "evening_miss_ratio": f"Evening dose timing is {direction} risk",
        "cognitive_impairment": "Cognitive status is a risk factor",
        "is_cognitively_impaired": "Cognitive status is a risk factor",
        "has_high_alert_med": "High-alert medication requires close monitoring",
        "current_streak_days": f"Current adherence streak is {direction} risk",
        "adherence_trend_delta": f"Adherence trend is {direction} risk",
        "refill_days_late": f"Refill timing is {direction} risk",
        "app_opens_7d": f"App engagement is {direction} risk",
    }

    return messages.get(feature_name, f"{feature_name.replace('_', ' ')} is {direction} risk")
