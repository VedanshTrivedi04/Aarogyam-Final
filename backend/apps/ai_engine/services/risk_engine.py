"""
Risk Engine — Public Interface for Backend Agents
==================================================
This is the ONLY file other Django apps should import from ai_engine.
All inter-agent contracts are defined here.

Integration contract:
    from apps.ai_engine.services.risk_engine import RiskEngine

    result = RiskEngine.get_risk_score(patient_id="uuid-string")
    # Returns structured dict — always, never raises

Usage by agents:
    - AdherenceAgent  → on DOSE_LOGGED / DOSE_MISSED
    - CaregiverAgent  → to determine alert threshold
    - NotificationAgent → to personalize message content
    - AdminAgent      → for dashboard risk overview
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("medadhere.ai_engine.risk_engine")

# ---------------------------------------------------------------------------
# Public result types (simple dicts — no ORM coupling)
# ---------------------------------------------------------------------------

EMPTY_RISK_RESULT = {
    "patient_id": None,
    "risk_score": 0.35,
    "risk_level": "medium",
    "confidence": 0.10,
    "reasons": ["Risk assessment temporarily unavailable"],
    "source": "UNAVAILABLE",
    "is_advisory_only": True,
    "model_version": None,
    "computed_at": None,
}


class RiskEngine:
    """
    Public interface for AI risk scoring.
    All methods are safe — they return structured dicts and never raise.
    """

    @staticmethod
    def get_risk_score(
        patient_id: str,
        force_refresh: bool = False,
    ) -> dict:
        """
        Get current risk score for a patient.

        Checks DB cache first (valid for 24h).
        If stale/missing → runs inference synchronously.
        Always returns a valid dict.

        Args:
            patient_id: Patient UUID string
            force_refresh: If True, skip cache and recompute

        Returns:
            {
                patient_id, risk_score, risk_level, confidence,
                reasons, source, is_advisory_only, model_version, computed_at
            }
        """
        try:
            if not force_refresh:
                cached = _get_cached_score(patient_id)
                if cached:
                    return cached

            return _compute_and_store(patient_id)

        except Exception as e:
            logger.error(f"RiskEngine.get_risk_score failed for {patient_id}: {e}")
            return {**EMPTY_RISK_RESULT, "patient_id": patient_id}

    @staticmethod
    def get_risk_level(patient_id: str) -> str:
        """
        Ultra-fast method — returns just the risk level string.
        Uses fallback.quick_assess if no cached score available.
        """
        try:
            cached = _get_cached_score(patient_id)
            if cached:
                return cached["risk_level"]
        except Exception:
            pass

        # Ultra-minimal fallback using only miss counts
        try:
            missed_7d, adherence_7d = _get_quick_stats(patient_id)
            from apps.ai_engine.services.fallback import quick_assess
            return quick_assess(missed_7d=missed_7d, missed_30d=0, adherence_7d=adherence_7d)
        except Exception:
            return "medium"  # Safe default

    @staticmethod
    def batch_score_patients(patient_ids: List[str]) -> Dict[str, dict]:
        """
        Score multiple patients. Used by nightly batch job.
        Returns {patient_id: risk_result_dict}
        """
        results = {}
        for pid in patient_ids:
            try:
                results[pid] = _compute_and_store(pid)
            except Exception as e:
                logger.error(f"Batch scoring failed for {pid}: {e}")
                results[pid] = {**EMPTY_RISK_RESULT, "patient_id": pid}
        return results

    @staticmethod
    def is_high_risk(patient_id: str) -> bool:
        """Convenience predicate for escalation decision logic."""
        level = RiskEngine.get_risk_level(patient_id)
        return level in ("high", "critical")

    @staticmethod
    def generate_insights(patient_id: str, lang: str = "en") -> List[dict]:
        """
        Generate human-readable insights for a patient.
        Returns list of insight dicts — empty list on failure.
        """
        try:
            from apps.ai_engine.services.insight_engine import InsightEngine
            return InsightEngine.generate(patient_id, lang)
        except Exception as e:
            logger.error(f"Insight generation failed for {patient_id}: {e}")
            return []

    @staticmethod
    def generate_recommendations(patient_id: str, lang: str = "en") -> List[dict]:
        """
        Generate actionable recommendations based on current risk score.
        Returns list of recommendation dicts — empty list on failure.
        """
        try:
            from apps.ai_engine.services.recommendation_engine import RecommendationEngine
            return RecommendationEngine.generate(patient_id, lang)
        except Exception as e:
            logger.error(f"Recommendation generation failed for {patient_id}: {e}")
            return []


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_cached_score(patient_id: str) -> Optional[dict]:
    """Retrieve valid (unexpired) risk score from DB."""
    try:
        from apps.ai_engine.models import PatientRiskScore
        score = (
            PatientRiskScore.objects.filter(
                patient_id=patient_id,
                expires_at__gt=datetime.now(timezone.utc),
            )
            .order_by("-generated_at")
            .first()
        )
        if score is None:
            return None

        return {
            "patient_id": str(score.patient_id),
            "risk_score": float(score.risk_score),
            "risk_level": score.risk_level,
            "confidence": float(score.confidence) if score.confidence else 0.5,
            "reasons": [r for r in [score.top_reason_1, score.top_reason_2, score.top_reason_3] if r],
            "source": score.computed_by,
            "is_advisory_only": True,
            "model_version": score.model_version,
            "computed_at": score.generated_at.isoformat() if score.generated_at else None,
        }
    except Exception as e:
        logger.debug(f"Cache lookup failed for {patient_id}: {e}")
        return None


def _compute_and_store(patient_id: str) -> dict:
    """
    Full inference pipeline: fetch data → engineer features → infer → store → return.
    """
    events_df, prescriptions_data, patient_data, as_of = _fetch_patient_data(patient_id)

    from apps.ai_engine.services.inference import InferenceService
    svc = InferenceService.get_instance()

    result = svc.predict(
        patient_id=patient_id,
        events_df=events_df,
        prescriptions_data=prescriptions_data,
        patient_data=patient_data,
        as_of=as_of,
    )

    _persist_score(result)

    return result.to_dict()


def _fetch_patient_data(patient_id: str):
    """
    Fetch adherence events + prescriptions + patient profile from DB.
    Returns (events_df, prescriptions_data, patient_data, as_of).
    All failures return safe empty defaults.
    """
    import pandas as pd

    events_df = pd.DataFrame()
    prescriptions_data = []
    patient_data = {}
    as_of = datetime.now(timezone.utc)

    try:
        # ReminderJob + DoseLog — last 90 days
        from apps.scheduling.models import ReminderJob
        from django.utils import timezone as dj_timezone
        from django.db.models import F

        # Anchor the 90-day lookback to the patient's own most recent event,
        # not wall-clock now() — otherwise a patient whose entire history
        # predates the last 90 days (e.g. older demo/seed data) gets zero
        # events fetched before adaptive as_of below ever gets a chance to
        # run, and looks indistinguishable from a brand-new patient.
        latest_event = (
            ReminderJob.objects.filter(
                schedule__prescription__patient_id=patient_id,
                deleted_at__isnull=True,
            )
            .order_by("-scheduled_at")
            .values_list("scheduled_at", flat=True)
            .first()
        )
        fetch_anchor = min(dj_timezone.now(), latest_event) if latest_event else dj_timezone.now()
        cutoff = fetch_anchor - timedelta(days=90)
        qs = ReminderJob.objects.filter(
            schedule__prescription__patient_id=patient_id,
            scheduled_at__gte=cutoff,
            deleted_at__isnull=True,
        ).annotate(
            prescription_id=F("schedule__prescription_id"),
            taken_at=F("dose_log__taken_at"),
            log_method=F("dose_log__source"),
        ).values(
            "id",
            "prescription_id",
            "scheduled_at",
            "taken_at",
            "status",
            "log_method",
        )
        if qs.exists():
            events_df = pd.DataFrame(list(qs))
            events_df.rename(columns={"id": "event_id"}, inplace=True)

            # Compute delay_minutes in pandas
            events_df["scheduled_at"] = pd.to_datetime(events_df["scheduled_at"], utc=True)
            events_df["taken_at"] = pd.to_datetime(events_df["taken_at"], utc=True)
            events_df["delay_minutes"] = (events_df["taken_at"] - events_df["scheduled_at"]).dt.total_seconds() / 60.0

            # Adaptive as-of: if this patient has no events within the last 7
            # days (e.g. demo/historical data), anchor rolling windows to the
            # most recent scheduled event instead of wall-clock now(), so the
            # 7d/30d windows aren't silently empty for every patient.
            most_recent = events_df["scheduled_at"].max()
            recent_cutoff = as_of - timedelta(days=7)
            if pd.notna(most_recent) and most_recent < recent_cutoff:
                as_of = most_recent.to_pydatetime()

    except Exception as e:
        logger.warning(f"Could not fetch adherence events for {patient_id}: {e}")

    try:
        from apps.clinical.models import Prescription
        presc_qs = Prescription.objects.filter(
            patient_id=patient_id, is_active=True, deleted_at__isnull=True
        ).select_related("medication")
        for p in presc_qs:
            prescriptions_data.append(
                {
                    "prescription_id": str(p.id),
                    "medication_name": p.medication.name,
                    "drug_class": getattr(p.medication, "drug_class", ""),
                    "doses_per_day": p.schedules.count() or 1,
                    "is_critical": False,
                }
            )
    except Exception as e:
        logger.warning(f"Could not fetch prescriptions for {patient_id}: {e}")

    try:
        from apps.clinical.models import Patient
        p = Patient.objects.get(id=patient_id)
        patient_data = {
            "age": _calculate_age(p.date_of_birth),
            "cognitive_impairment": getattr(p, "cognitive_status", "NORMAL") not in ("NORMAL",),
        }
    except Exception as e:
        logger.warning(f"Could not fetch patient profile for {patient_id}: {e}")

    return events_df, prescriptions_data, patient_data, as_of


def _persist_score(result) -> None:
    """Save risk score to DB. Non-blocking — failures logged but not raised."""
    try:
        from apps.ai_engine.models import AIModelRegistry, PatientRiskScore

        model_record = None
        if result.model_version:
            model_record = AIModelRegistry.objects.filter(
                model_version=result.model_version
            ).first()

        # Extract feature snapshot written alongside the score so InsightEngine
        # can read real values from DB without re-computing features.
        snap = result.feature_snapshot or {}

        PatientRiskScore.objects.create(
            patient_id=result.patient_id,
            period_start=(datetime.now(timezone.utc) - timedelta(days=30)).date(),
            period_end=datetime.now(timezone.utc).date(),
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            confidence=result.confidence,
            top_reason_1=result.reasons[0] if len(result.reasons) > 0 else None,
            top_reason_2=result.reasons[1] if len(result.reasons) > 1 else None,
            top_reason_3=result.reasons[2] if len(result.reasons) > 2 else None,
            # ── Feature snapshot ─────────────────────────────────────────────
            feature_adherence_7d=snap.get("adherence_rate_7d"),
            feature_adherence_30d=snap.get("adherence_rate_30d"),
            feature_avg_delay_min=snap.get("avg_delay_minutes"),
            feature_skip_count_7d=snap.get("skip_count_7d"),
            feature_missed_count_7d=snap.get("missed_count_7d"),
            feature_regimen_complexity=snap.get("doses_per_day"),
            feature_app_opens_7d=snap.get("app_opens_7d"),
            feature_refill_days_late=snap.get("refill_days_late"),
            feature_weekend_miss_ratio=snap.get("weekend_miss_ratio"),
            # ── Provenance ───────────────────────────────────────────────────
            model=model_record,
            model_version=result.model_version or "fallback",
            computed_by=result.source,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    except Exception as e:
        logger.warning(f"Could not persist risk score for {result.patient_id}: {e}")


def _get_quick_stats(patient_id: str):
    """Minimal DB query for quick_assess fallback."""
    try:
        from apps.scheduling.models import ReminderJob
        from django.utils import timezone
        from django.db.models import Count, Q

        cutoff_7d = timezone.now() - timedelta(days=7)
        qs = ReminderJob.objects.filter(
            schedule__prescription__patient_id=patient_id, scheduled_at__gte=cutoff_7d
        )
        total = qs.count()
        missed = qs.filter(status="MISSED").count()
        taken = total - missed
        adherence = taken / total if total > 0 else 1.0
        return missed, adherence
    except Exception:
        return 0, 1.0


def _calculate_age(date_of_birth) -> int:
    if not date_of_birth:
        return 45
    today = datetime.now(timezone.utc).date()
    return (today - date_of_birth).days // 365
