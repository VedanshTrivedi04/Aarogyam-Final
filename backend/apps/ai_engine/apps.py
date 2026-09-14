from django.apps import AppConfig
import os


class AIEngineConfig(AppConfig):
    name = "apps.ai_engine"
    label = "ai_engine"
    verbose_name = "AI Engine"

    def ready(self):
        """
        Bootstrap the AI engine on Django startup.
        - Models are loaded lazily on-demand to conserve memory on free tier hosting (512MB limit).
        - Set AI_WARMUP_ON_STARTUP=True in environment to eagerly preload model.
        """
        if os.environ.get("AI_WARMUP_ON_STARTUP", "False").lower() == "true":
            try:
                from apps.ai_engine.services.inference import InferenceService
                InferenceService.warmup()
            except Exception as e:
                import logging
                logger = logging.getLogger("medadhere.ai_engine")
                logger.warning(f"AI Engine warmup skipped: {e}")
