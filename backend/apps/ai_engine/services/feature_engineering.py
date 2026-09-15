"""
Feature Engineering Pipeline
=============================
Transforms raw adherence history into ML-ready features.
Called by both training pipeline (bulk) and inference pipeline (per-patient, real-time).

Design principles:
  - Pure functions wherever possible (testable, no DB side effects)
  - Handles missing data gracefully (returns safe defaults)
  - Output is always a flat dict — no NaN, no None
  - Same code path for training and inference (no leakage risk)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("medadhere.ai_engine.features")

# ---------------------------------------------------------------------------
# Feature schema — every feature with its safe default
# ---------------------------------------------------------------------------
FEATURE_DEFAULTS: Dict[str, Any] = {
    # Short-term adherence
    "adherence_rate_7d": 1.0,
    "adherence_rate_14d": 1.0,
    "adherence_rate_30d": 1.0,
    "adherence_rate_90d": 1.0,
    # Miss counts
    "missed_count_7d": 0,
    "missed_count_14d": 0,
    "missed_count_30d": 0,
    "skip_count_7d": 0,
    # Timing
    "avg_delay_minutes": 0.0,
    "max_delay_minutes": 0.0,
    "pct_on_time_7d": 1.0,
    # Streak
    "current_streak_days": 0,
    "max_streak_30d": 0,
    # Capped to the 90-day lookback window (not an arbitrary large sentinel
    # like 999) — a value trees never see in training is out-of-distribution
    # and extrapolates unpredictably, which is how a genuinely zero-miss
    # patient could end up with a wildly wrong (high) risk prediction.
    "days_since_last_miss": 90,
    # Regimen complexity
    "medication_count": 1,
    "doses_per_day": 1,
    "has_high_alert_med": 0,
    # Temporal patterns
    "weekend_miss_ratio": 0.0,
    "evening_miss_ratio": 0.0,
    "morning_miss_ratio": 0.0,
    "time_of_day_risk": 0.0,
    # Behavioral signals
    "app_opens_7d": 7,
    "refill_days_late": 0,
    "consecutive_miss_streak": 0,
    # Patient context
    "patient_age_group": 1,  # 0=<40, 1=40-65, 2=65+
    "is_cognitively_impaired": 0,
    # Trend
    "adherence_trend_delta": 0.0,  # 30d vs 7d — positive = improving
}

FEATURE_NAMES = list(FEATURE_DEFAULTS.keys())


@dataclass
class FeatureVector:
    patient_id: str
    features: Dict[str, Any] = field(default_factory=lambda: dict(FEATURE_DEFAULTS))
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_quality_score: float = 1.0  # 0-1, lower = less data available

    def to_array(self) -> np.ndarray:
        return np.array([self.features.get(k, FEATURE_DEFAULTS[k]) for k in FEATURE_NAMES])

    def to_dict(self) -> Dict[str, Any]:
        return {**self.features, "patient_id": self.patient_id}


# ---------------------------------------------------------------------------
# Core feature computation
# ---------------------------------------------------------------------------


def compute_adherence_rates(
    events: pd.DataFrame, as_of: Optional[datetime] = None
) -> Dict[str, float]:
    """Compute adherence rates for multiple time windows."""
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    if events.empty:
        return {
            "adherence_rate_7d": FEATURE_DEFAULTS["adherence_rate_7d"],
            "adherence_rate_14d": FEATURE_DEFAULTS["adherence_rate_14d"],
            "adherence_rate_30d": FEATURE_DEFAULTS["adherence_rate_30d"],
            "adherence_rate_90d": FEATURE_DEFAULTS["adherence_rate_90d"],
        }

    taken_statuses = {"TAKEN", "TAKEN_LATE", "TAKEN_EARLY"}
    results = {}

    for days, key in [(7, "7d"), (14, "14d"), (30, "30d"), (90, "90d")]:
        cutoff = as_of - timedelta(days=days)
        window = events[events["scheduled_at"] >= cutoff]
        if len(window) == 0:
            results[f"adherence_rate_{key}"] = FEATURE_DEFAULTS[f"adherence_rate_{key}"]
        else:
            taken = window[window["status"].isin(taken_statuses)].shape[0]
            results[f"adherence_rate_{key}"] = round(taken / len(window), 4)

    return results


def compute_miss_counts(
    events: pd.DataFrame, as_of: Optional[datetime] = None
) -> Dict[str, int]:
    """Count missed and skipped doses in time windows."""
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    if events.empty:
        return {
            "missed_count_7d": 0,
            "missed_count_14d": 0,
            "missed_count_30d": 0,
            "skip_count_7d": 0,
        }

    results = {}
    for days, key in [(7, "7d"), (14, "14d"), (30, "30d")]:
        cutoff = as_of - timedelta(days=days)
        window = events[events["scheduled_at"] >= cutoff]
        results[f"missed_count_{key}"] = int(
            window[window["status"] == "MISSED"].shape[0]
        )

    cutoff_7d = as_of - timedelta(days=7)
    w7 = events[events["scheduled_at"] >= cutoff_7d]
    results["skip_count_7d"] = int(w7[w7["status"] == "SKIPPED"].shape[0])

    return results


def compute_timing_features(events: pd.DataFrame) -> Dict[str, float]:
    """Compute delay statistics from taken doses."""
    if events.empty or "status" not in events.columns or "delay_minutes" not in events.columns:
        return {
            "avg_delay_minutes": FEATURE_DEFAULTS["avg_delay_minutes"],
            "max_delay_minutes": FEATURE_DEFAULTS["max_delay_minutes"],
            "pct_on_time_7d": FEATURE_DEFAULTS["pct_on_time_7d"],
        }

    taken = events[
        events["status"].isin({"TAKEN", "TAKEN_LATE", "TAKEN_EARLY"})
        & events["delay_minutes"].notna()
    ]

    if taken.empty:
        return {
            "avg_delay_minutes": FEATURE_DEFAULTS["avg_delay_minutes"],
            "max_delay_minutes": FEATURE_DEFAULTS["max_delay_minutes"],
            "pct_on_time_7d": FEATURE_DEFAULTS["pct_on_time_7d"],
        }

    avg_delay = float(taken["delay_minutes"].mean())
    max_delay = float(taken["delay_minutes"].max())
    on_time = taken[taken["delay_minutes"].abs() <= 30].shape[0]
    pct_on_time = round(on_time / len(taken), 4) if len(taken) > 0 else 1.0

    return {
        "avg_delay_minutes": round(avg_delay, 2),
        "max_delay_minutes": round(max_delay, 2),
        "pct_on_time_7d": pct_on_time,
    }


def compute_streak_features(
    events: pd.DataFrame, as_of: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Compute streak metrics.
    A streak is broken if any scheduled dose on a calendar day is MISSED.
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    if events.empty:
        return {
            "current_streak_days": 0,
            "max_streak_30d": 0,
            "days_since_last_miss": FEATURE_DEFAULTS["days_since_last_miss"],
            "consecutive_miss_streak": 0,
        }

    events = events.copy()
    events["date"] = pd.to_datetime(events["scheduled_at"]).dt.date
    events_sorted = events.sort_values("scheduled_at")

    # days_since_last_miss
    missed = events[events["status"] == "MISSED"]
    if missed.empty:
        # No miss anywhere in the observed history — report how much clean
        # history we actually have (capped to the lookback window) rather
        # than an arbitrary sentinel that never occurs in training data.
        earliest = pd.to_datetime(events["scheduled_at"]).min()
        observed_days = max(0, (as_of - earliest).days)
        days_since_last_miss = min(observed_days, FEATURE_DEFAULTS["days_since_last_miss"])
    else:
        last_miss_date = pd.to_datetime(missed["scheduled_at"]).max()
        days_since_last_miss = max(0, (as_of - last_miss_date).days)

    # Consecutive miss streak (most recent)
    consecutive_miss = 0
    for _, row in events_sorted.iloc[::-1].iterrows():
        if row["status"] == "MISSED":
            consecutive_miss += 1
        else:
            break

    # Current adherent streak (days)
    dates = events["date"].unique()
    dates_sorted = sorted(dates, reverse=True)
    current_streak = 0
    for d in dates_sorted:
        day_events = events[events["date"] == d]
        all_taken = day_events["status"].isin({"TAKEN", "TAKEN_LATE", "TAKEN_EARLY"}).all()
        if all_taken:
            current_streak += 1
        else:
            break

    # Max streak in last 30 days
    cutoff_30d = as_of.date() - timedelta(days=30)
    recent = events[events["date"] >= cutoff_30d]
    recent_dates = sorted(recent["date"].unique())
    max_streak = 0
    streak = 0
    for d in recent_dates:
        day_events = recent[recent["date"] == d]
        all_taken = day_events["status"].isin({"TAKEN", "TAKEN_LATE", "TAKEN_EARLY"}).all()
        if all_taken:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    return {
        "current_streak_days": current_streak,
        "max_streak_30d": max_streak,
        "days_since_last_miss": days_since_last_miss,
        "consecutive_miss_streak": consecutive_miss,
    }


def compute_temporal_patterns(events: pd.DataFrame) -> Dict[str, float]:
    """
    Compute time-based miss patterns.
    Weekend effect, evening effect, morning effect.
    """
    if events.empty:
        return {
            "weekend_miss_ratio": 0.0,
            "evening_miss_ratio": 0.0,
            "morning_miss_ratio": 0.0,
            "time_of_day_risk": 0.0,
        }

    events = events.copy()
    events["dt"] = pd.to_datetime(events["scheduled_at"])
    events["is_weekend"] = events["dt"].dt.dayofweek >= 5
    events["hour"] = events["dt"].dt.hour

    def miss_ratio(subset: pd.DataFrame) -> float:
        if subset.empty:
            return 0.0
        return round(subset[subset["status"] == "MISSED"].shape[0] / len(subset), 4)

    weekend_events = events[events["is_weekend"]]
    weekday_events = events[~events["is_weekend"]]
    evening_events = events[events["hour"] >= 18]
    morning_events = events[events["hour"] < 10]

    weekend_miss = miss_ratio(weekend_events)
    weekday_miss = miss_ratio(weekday_events)
    evening_miss = miss_ratio(evening_events)
    morning_miss = miss_ratio(morning_events)

    # Time of day risk: 0=low, 1=high (based on peak miss hours)
    late_night = events[(events["hour"] >= 21) | (events["hour"] < 6)]
    tod_risk = miss_ratio(late_night)

    return {
        "weekend_miss_ratio": weekend_miss,
        "evening_miss_ratio": evening_miss,
        "morning_miss_ratio": morning_miss,
        "time_of_day_risk": tod_risk,
    }


def compute_regimen_complexity(prescriptions_data: List[Dict]) -> Dict[str, Any]:
    """Compute schedule complexity features from prescription data."""
    if not prescriptions_data:
        return {
            "medication_count": 1,
            "doses_per_day": 1,
            "has_high_alert_med": 0,
        }

    high_alert_classes = {"Anticoagulant", "Insulin", "Antiepileptic", "Immunosuppressant"}
    has_high_alert = any(
        p.get("drug_class", "") in high_alert_classes for p in prescriptions_data
    )
    total_doses = sum(p.get("doses_per_day", 1) for p in prescriptions_data)

    return {
        "medication_count": len(prescriptions_data),
        "doses_per_day": total_doses,
        "has_high_alert_med": int(has_high_alert),
    }


def compute_patient_context(patient_data: Dict) -> Dict[str, Any]:
    """Extract patient demographic/clinical context features."""
    age = patient_data.get("age", 45)
    age_group = 0 if age < 40 else (1 if age < 65 else 2)

    return {
        "patient_age_group": age_group,
        "is_cognitively_impaired": int(patient_data.get("cognitive_impairment", False)),
    }


def compute_trend(features: Dict) -> Dict[str, float]:
    """Compute adherence trend: positive = improving, negative = worsening."""
    rate_7d = features.get("adherence_rate_7d", 1.0)
    rate_30d = features.get("adherence_rate_30d", 1.0)
    delta = round(rate_7d - rate_30d, 4)  # positive = recent better than historical
    return {"adherence_trend_delta": delta}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def build_feature_vector(
    patient_id: str,
    events_df: pd.DataFrame,
    prescriptions_data: Optional[List[Dict]] = None,
    patient_data: Optional[Dict] = None,
    app_opens_7d: int = 7,
    refill_days_late: int = 0,
    as_of: Optional[datetime] = None,
) -> FeatureVector:
    """
    Compute all features for a single patient.

    Args:
        patient_id: Patient UUID
        events_df: DataFrame of adherence_events for this patient
        prescriptions_data: List of prescription dicts (with drug_class, doses_per_day)
        patient_data: Patient profile dict (age, cognitive_impairment, etc.)
        app_opens_7d: App engagement metric
        refill_days_late: Days late on last refill
        as_of: Reference datetime for time windows (default: now)

    Returns:
        FeatureVector with all features filled and safe defaults applied
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    features = dict(FEATURE_DEFAULTS)

    # Ensure scheduled_at is datetime, and drop not-yet-due events (future
    # PENDING reminder jobs) — they haven't happened yet so counting them as
    # "not taken" would artificially deflate adherence for every patient with
    # upcoming scheduled doses.
    if not events_df.empty and "scheduled_at" in events_df.columns:
        events_df = events_df.copy()
        events_df["scheduled_at"] = pd.to_datetime(events_df["scheduled_at"], utc=True)
        as_of_ts = pd.Timestamp(as_of)
        if as_of_ts.tzinfo is None:
            as_of_ts = as_of_ts.tz_localize("UTC")
        events_df = events_df[events_df["scheduled_at"] <= as_of_ts]

    # Data quality: fewer events = less reliable features
    data_quality = min(1.0, len(events_df) / 30.0) if not events_df.empty else 0.0

    try:
        features.update(compute_adherence_rates(events_df, as_of))
    except Exception as e:
        logger.warning(f"adherence_rates failed for {patient_id}: {e}")

    try:
        features.update(compute_miss_counts(events_df, as_of))
    except Exception as e:
        logger.warning(f"miss_counts failed for {patient_id}: {e}")

    try:
        features.update(compute_timing_features(events_df))
    except Exception as e:
        logger.warning(f"timing_features failed for {patient_id}: {e}")

    try:
        features.update(compute_streak_features(events_df, as_of))
    except Exception as e:
        logger.warning(f"streak_features failed for {patient_id}: {e}")

    try:
        features.update(compute_temporal_patterns(events_df))
    except Exception as e:
        logger.warning(f"temporal_patterns failed for {patient_id}: {e}")

    try:
        features.update(compute_regimen_complexity(prescriptions_data or []))
    except Exception as e:
        logger.warning(f"regimen_complexity failed for {patient_id}: {e}")

    try:
        features.update(compute_patient_context(patient_data or {}))
    except Exception as e:
        logger.warning(f"patient_context failed for {patient_id}: {e}")

    try:
        features.update(compute_trend(features))
    except Exception as e:
        logger.warning(f"trend failed for {patient_id}: {e}")

    # Behavioral signals
    features["app_opens_7d"] = app_opens_7d
    features["refill_days_late"] = refill_days_late

    # Guarantee no None values
    for k, v in features.items():
        if v is None or (isinstance(v, float) and np.isnan(v)):
            features[k] = FEATURE_DEFAULTS.get(k, 0)

    return FeatureVector(
        patient_id=patient_id,
        features=features,
        computed_at=as_of,
        data_quality_score=data_quality,
    )


def build_training_features(adherence_df: pd.DataFrame, holdout_days: int = 14) -> pd.DataFrame:
    """
    Build feature matrix from full adherence DataFrame (for training).
    Groups by patient_id and computes features per patient.
    Returns DataFrame with one row per patient.

    Labels come from a held-out FUTURE window, not from the feature window
    itself. Deriving the label directly from a thresholded feature (e.g.
    "adherence_rate_7d < 0.80") makes the label a deterministic function of
    one of the model's own inputs — the model then trivially learns that one
    threshold and outputs a near-constant probability on either side of it
    instead of a real risk gradient (this is how the model ended up
    predicting ~the same score for almost everyone). Holding out the last
    `holdout_days` of each patient's history and predicting *that* from
    everything before it turns this into a genuine forecasting task.
    """
    results = []
    patient_ids = adherence_df["patient_id"].unique()
    logger.info(f"Building features for {len(patient_ids):,} patients...")
    taken_statuses = {"TAKEN", "TAKEN_LATE", "TAKEN_EARLY"}
    skipped_patients = 0

    for pid in patient_ids:
        patient_events = adherence_df[adherence_df["patient_id"] == pid].copy()
        patient_events["scheduled_at"] = pd.to_datetime(patient_events["scheduled_at"], utc=True)

        cutoff = patient_events["scheduled_at"].max() - timedelta(days=holdout_days)
        history = patient_events[patient_events["scheduled_at"] <= cutoff]
        future = patient_events[patient_events["scheduled_at"] > cutoff]

        if history.empty or future.empty:
            skipped_patients += 1
            continue

        # Get patient context from first row
        first_row = patient_events.iloc[0]
        patient_data = {
            "age": first_row.get("patient_age", 45),
            "cognitive_impairment": first_row.get("cognitive_impairment", False),
        }

        fv = build_feature_vector(
            patient_id=pid,
            events_df=history,
            patient_data=patient_data,
            as_of=cutoff.to_pydatetime(),
        )

        future_adherence = float(future["status"].isin(taken_statuses).mean())
        row = fv.to_dict()
        row["label"] = int(future_adherence < 0.80)
        results.append(row)

    if skipped_patients:
        logger.info(f"Skipped {skipped_patients} patients with insufficient history/future split")

    df = pd.DataFrame(results)
    logger.info(
        f"Feature matrix: {df.shape} | Non-adherent: {df['label'].sum()} ({df['label'].mean():.1%})"
    )
    return df
