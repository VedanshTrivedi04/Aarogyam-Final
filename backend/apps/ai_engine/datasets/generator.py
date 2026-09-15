"""
Synthetic Data Generator
========================
Generates realistic medication adherence training data.
No real patient data required — this simulates clinically plausible behavior.

Realistic patterns included:
  - Elderly patients → more missed doses
  - Complex regimens → lower overall adherence
  - Weekends → higher miss probability
  - Late-night doses (>21:00) → frequently missed
  - Morning doses on weekdays → mostly taken
  - Patients with cognitive impairment → very erratic
  - Side-effect skips → medication-specific

Run:
    python -m apps.ai_engine.datasets.generator --patients 10000 --days 90
"""

import argparse
import json
import logging
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("medadhere.ai_engine.generator")


# ---------------------------------------------------------------------------
# Patient archetypes — drive base adherence probability
# ---------------------------------------------------------------------------

ARCHETYPES = {
    "elderly_complex": {
        "weight": 0.15,
        "base_adherence": 0.55,
        "condition_count_range": (3, 6),
        "meds_per_day_range": (4, 8),
        "age_range": (68, 90),
        "cognitive_impairment_prob": 0.40,
    },
    "elderly_simple": {
        "weight": 0.15,
        "base_adherence": 0.72,
        "condition_count_range": (1, 3),
        "meds_per_day_range": (1, 3),
        "age_range": (65, 85),
        "cognitive_impairment_prob": 0.15,
    },
    "middle_aged_chronic": {
        "weight": 0.15,
        "base_adherence": 0.78,
        "condition_count_range": (1, 3),
        "meds_per_day_range": (1, 4),
        "age_range": (40, 65),
        "cognitive_impairment_prob": 0.02,
    },
    "highly_adherent": {
        "weight": 0.15,
        "base_adherence": 0.96,
        "condition_count_range": (1, 2),
        "meds_per_day_range": (1, 2),
        "age_range": (25, 60),
        "cognitive_impairment_prob": 0.00,
    },
    "young_acute": {
        "weight": 0.20,
        "base_adherence": 0.85,
        "condition_count_range": (1, 2),
        "meds_per_day_range": (1, 2),
        "age_range": (18, 40),
        "cognitive_impairment_prob": 0.00,
    },
    "non_adherent_profile": {
        "weight": 0.20,
        "base_adherence": 0.40,
        "condition_count_range": (2, 5),
        "meds_per_day_range": (2, 6),
        "age_range": (25, 70),
        "cognitive_impairment_prob": 0.10,
    },
}

MEDICATIONS = [
    {"name": "Metformin", "drug_class": "Biguanide", "side_effect_skip_prob": 0.08},
    {"name": "Amlodipine", "drug_class": "CCB", "side_effect_skip_prob": 0.04},
    {"name": "Atorvastatin", "drug_class": "Statin", "side_effect_skip_prob": 0.06},
    {"name": "Lisinopril", "drug_class": "ACE Inhibitor", "side_effect_skip_prob": 0.05},
    {"name": "Aspirin", "drug_class": "Antiplatelet", "side_effect_skip_prob": 0.03},
    {"name": "Metoprolol", "drug_class": "Beta Blocker", "side_effect_skip_prob": 0.05},
    {"name": "Omeprazole", "drug_class": "PPI", "side_effect_skip_prob": 0.02},
    {"name": "Levothyroxine", "drug_class": "Thyroid", "side_effect_skip_prob": 0.01},
    {"name": "Warfarin", "drug_class": "Anticoagulant", "side_effect_skip_prob": 0.03},
    {"name": "Insulin Glargine", "drug_class": "Insulin", "side_effect_skip_prob": 0.04},
    {"name": "Salbutamol", "drug_class": "Bronchodilator", "side_effect_skip_prob": 0.02},
    {"name": "Sertraline", "drug_class": "SSRI", "side_effect_skip_prob": 0.09},
]

DOSE_TIMES = [
    time(6, 0),
    time(8, 0),
    time(10, 0),
    time(13, 0),
    time(18, 0),
    time(21, 0),
    time(22, 0),
    time(23, 0),
]


@dataclass
class SyntheticPatient:
    patient_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    age: int = 45
    archetype: str = "middle_aged_chronic"
    base_adherence: float = 0.78
    cognitive_impairment: bool = False
    medication_count: int = 2
    doses_per_day: int = 2


@dataclass
class SyntheticPrescription:
    prescription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str = ""
    medication_name: str = "Metformin"
    drug_class: str = "Biguanide"
    side_effect_skip_prob: float = 0.05
    dose_times: List[time] = field(default_factory=list)
    start_date: date = field(default_factory=date.today)


@dataclass
class AdherenceRecord:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str = ""
    prescription_id: str = ""
    medication_name: str = ""
    scheduled_at: datetime = field(default_factory=datetime.now)
    taken_at: Optional[datetime] = None
    status: str = "TAKEN"  # TAKEN | MISSED | SKIPPED | TAKEN_LATE | TAKEN_EARLY
    skip_reason: Optional[str] = None
    delay_minutes: Optional[int] = None
    is_weekend: bool = False
    hour_of_day: int = 8
    dose_count_for_patient: int = 1


def _select_archetype() -> tuple:
    """Weighted random archetype selection."""
    names = list(ARCHETYPES.keys())
    weights = [ARCHETYPES[n]["weight"] for n in names]
    chosen = random.choices(names, weights=weights, k=1)[0]
    return chosen, ARCHETYPES[chosen]


def _compute_adherence_probability(
    patient: SyntheticPatient,
    prescription: SyntheticPrescription,
    dt: datetime,
    day_index: int,
) -> float:
    """
    Compute take probability for a specific dose slot.
    Incorporates all realistic patterns.
    """
    p = patient.base_adherence

    # Cognitive impairment penalty — stable per-patient trait, applied directly
    if patient.cognitive_impairment:
        p -= 0.20

    # Situational penalties (complexity, timing, side effects, fatigue) stack
    # per-dose and can otherwise erase 0.5+ of probability, dragging the whole
    # population's realized adherence far below each archetype's intended
    # base_adherence. Cap their combined effect so the population stays
    # anchored near the archetypes' intended spread instead of collapsing
    # almost everyone into "non-adherent".
    situational_penalty = 0.0

    # Medication complexity penalty (more meds → lower per-med adherence)
    situational_penalty += min((patient.medication_count - 1) * 0.015, 0.10)

    # Weekend effect
    if dt.weekday() >= 5:
        situational_penalty += 0.05

    # Time-of-day penalties
    hour = dt.hour
    if hour >= 21:
        situational_penalty += 0.08  # late night doses often skipped
    elif hour >= 18:
        situational_penalty += 0.04  # evening slightly worse
    elif hour <= 7:
        situational_penalty += 0.02  # very early morning

    # Side effect skip probability
    situational_penalty += prescription.side_effect_skip_prob

    # Temporal fatigue — adherence degrades slightly over long treatments
    situational_penalty += min(day_index / 90 * 0.08, 0.08)

    p -= min(situational_penalty, 0.25)

    # Streak boost — if last 3 days were all taken, small boost
    # (simplified approximation here)
    if day_index > 3 and random.random() < 0.3:
        p += 0.05

    return max(0.05, min(0.99, p))


def _generate_delay(probability: float, dt: datetime) -> tuple:
    """
    Generate dose timing given a take probability.
    Returns (status, taken_at, delay_minutes).
    """
    if random.random() > probability:
        # Not taken
        reason = random.choices(
            ["FORGOT", "SIDE_EFFECTS", "RAN_OUT", "COST", "FELT_BETTER", "OTHER"],
            weights=[0.45, 0.20, 0.12, 0.08, 0.10, 0.05],
        )[0]
        return "MISSED", None, None, reason

    # Taken — determine timing
    delay = int(np.random.normal(loc=5, scale=25))  # mean 5 min late, SD 25
    delay = max(-30, min(240, delay))  # clamp [-30, 240]

    taken_at = dt + timedelta(minutes=delay)

    if delay < -15:
        status = "TAKEN_EARLY"
    elif delay > 60:
        status = "TAKEN_LATE"
    else:
        status = "TAKEN"

    return status, taken_at, delay, None


def generate_patients(n_patients: int = 10_000) -> List[SyntheticPatient]:
    """Generate synthetic patient population."""
    patients = []
    for _ in range(n_patients):
        archetype_name, arch = _select_archetype()
        age = random.randint(*arch["age_range"])
        base_adherence = arch["base_adherence"] + np.random.normal(0, 0.08)
        base_adherence = max(0.10, min(0.99, base_adherence))
        cognitive = random.random() < arch["cognitive_impairment_prob"]
        med_count = random.randint(*arch["condition_count_range"])
        doses = random.randint(*arch["meds_per_day_range"])

        patients.append(
            SyntheticPatient(
                age=age,
                archetype=archetype_name,
                base_adherence=base_adherence,
                cognitive_impairment=cognitive,
                medication_count=med_count,
                doses_per_day=doses,
            )
        )

    logger.info(f"Generated {len(patients)} synthetic patients")
    return patients


def generate_prescriptions(
    patients: List[SyntheticPatient],
    start_date: date,
) -> List[SyntheticPrescription]:
    """Assign medications + schedules to patients."""
    prescriptions = []
    for patient in patients:
        meds = random.sample(MEDICATIONS, k=min(patient.medication_count, len(MEDICATIONS)))
        times_pool = random.sample(DOSE_TIMES, k=min(patient.doses_per_day, len(DOSE_TIMES)))

        for i, med in enumerate(meds):
            # Assign dose time(s) to each med
            med_times = [times_pool[i % len(times_pool)]]
            if patient.doses_per_day >= 2 and i < 2:
                med_times = [DOSE_TIMES[1], DOSE_TIMES[4]]  # morning + evening

            prescriptions.append(
                SyntheticPrescription(
                    patient_id=patient.patient_id,
                    medication_name=med["name"],
                    drug_class=med["drug_class"],
                    side_effect_skip_prob=med["side_effect_skip_prob"],
                    dose_times=med_times,
                    start_date=start_date,
                )
            )

    logger.info(f"Generated {len(prescriptions)} synthetic prescriptions")
    return prescriptions


def generate_adherence_history(
    patients: List[SyntheticPatient],
    prescriptions: List[SyntheticPrescription],
    n_days: int = 90,
    start_date: Optional[date] = None,
) -> pd.DataFrame:
    """
    Generate full adherence event history.
    Returns DataFrame matching telemetry.adherence_events schema.
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=n_days)

    patient_map = {p.patient_id: p for p in patients}
    records = []

    for presc in prescriptions:
        patient = patient_map[presc.patient_id]

        for day_offset in range(n_days):
            current_date = start_date + timedelta(days=day_offset)

            for dose_time in presc.dose_times:
                scheduled_dt = datetime.combine(current_date, dose_time)
                prob = _compute_adherence_probability(patient, presc, scheduled_dt, day_offset)
                status, taken_at, delay, skip_reason = _generate_delay(prob, scheduled_dt)

                records.append(
                    {
                        "event_id": str(uuid.uuid4()),
                        "patient_id": presc.patient_id,
                        "prescription_id": presc.prescription_id,
                        "medication_name": presc.medication_name,
                        "drug_class": presc.drug_class,
                        "scheduled_at": scheduled_dt.isoformat(),
                        "taken_at": taken_at.isoformat() if taken_at else None,
                        "status": status,
                        "skip_reason": skip_reason,
                        "delay_minutes": delay,
                        "is_weekend": current_date.weekday() >= 5,
                        "hour_of_day": dose_time.hour,
                        "patient_age": patient.age,
                        "patient_archetype": patient.archetype,
                        "cognitive_impairment": patient.cognitive_impairment,
                        "medication_count": patient.medication_count,
                        "doses_per_day": patient.doses_per_day,
                        "day_index": day_offset,
                    }
                )

    df = pd.DataFrame(records)
    logger.info(
        f"Generated {len(df):,} adherence events "
        f"({df[df.status == 'MISSED'].shape[0]:,} missed, "
        f"{df[df.status == 'TAKEN'].shape[0]:,} taken)"
    )
    return df


def generate_dataset(
    n_patients: int = 10_000,
    n_days: int = 90,
    output_dir: str = "apps/ai_engine/datasets/raw",
) -> dict:
    """
    Full dataset generation pipeline.
    Returns dict with patients, prescriptions, adherence DataFrames.
    """
    os.makedirs(output_dir, exist_ok=True)
    start_date = date.today() - timedelta(days=n_days)

    logger.info(f"Starting dataset generation: {n_patients} patients, {n_days} days")

    patients = generate_patients(n_patients)
    prescriptions = generate_prescriptions(patients, start_date)
    adherence_df = generate_adherence_history(patients, prescriptions, n_days, start_date)

    # Save to disk
    patients_df = pd.DataFrame([p.__dict__ for p in patients])
    presc_df = pd.DataFrame(
        [
            {
                "prescription_id": p.prescription_id,
                "patient_id": p.patient_id,
                "medication_name": p.medication_name,
                "drug_class": p.drug_class,
                "dose_times": json.dumps([t.isoformat() for t in p.dose_times]),
                "start_date": p.start_date.isoformat(),
            }
            for p in prescriptions
        ]
    )

    patients_df.to_csv(f"{output_dir}/patients.csv", index=False)
    presc_df.to_csv(f"{output_dir}/prescriptions.csv", index=False)
    adherence_df.to_csv(f"{output_dir}/adherence_events.csv", index=False)

    stats = {
        "n_patients": len(patients),
        "n_prescriptions": len(prescriptions),
        "n_events": len(adherence_df),
        "overall_adherence_rate": round(
            adherence_df[adherence_df.status.isin(["TAKEN", "TAKEN_LATE"])].shape[0]
            / len(adherence_df)
            * 100,
            2,
        ),
        "miss_rate": round(
            adherence_df[adherence_df.status == "MISSED"].shape[0] / len(adherence_df) * 100, 2
        ),
    }

    with open(f"{output_dir}/stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    logger.info(f"Dataset saved to {output_dir}")
    logger.info(f"Stats: {stats}")

    return {"patients": patients_df, "prescriptions": presc_df, "adherence": adherence_df, "stats": stats}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Generate synthetic adherence dataset")
    parser.add_argument("--patients", type=int, default=10_000)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output", default="apps/ai_engine/datasets/raw")
    args = parser.parse_args()

    result = generate_dataset(
        n_patients=args.patients,
        n_days=args.days,
        output_dir=args.output,
    )
    print(json.dumps(result["stats"], indent=2))
