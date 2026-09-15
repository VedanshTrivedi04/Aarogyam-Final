"""
Model Training Pipeline
========================
Trains the XGBoost adherence risk prediction model.
Saves versioned artifacts, evaluates performance, and registers in DB.

Usage:
    # From CLI
    python -m apps.ai_engine.services.training

    # From Django management command
    python manage.py ai_train --model-version 1.0.0

Design:
    - Reads synthetic (or real) adherence data
    - Engineers features via feature_engineering.py
    - Trains XGBoost binary classifier
    - Computes SHAP values for explainability
    - Saves model + metadata with version tag
    - Registers in ai_engine.model_registry
"""

import json
import logging
import os
import pickle
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("medadhere.ai_engine.training")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_MODEL_DIR = os.environ.get("AI_MODEL_DIR", "apps/ai_engine/models/artifacts")
DEFAULT_DATA_DIR = os.environ.get("AI_DATA_DIR", "apps/ai_engine/datasets/raw")


@dataclass
class TrainingConfig:
    model_version: str = "1.0.0"
    model_name: str = "adherence_risk_xgb"
    test_size: float = 0.20
    val_size: float = 0.10
    random_state: int = 42
    n_estimators: int = 300
    max_depth: int = 6
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    scale_pos_weight: float = 2.0  # handle class imbalance
    early_stopping_rounds: int = 30
    eval_metric: str = "auc"


@dataclass
class TrainingResult:
    model_version: str
    auc_roc: float
    f1_score: float
    precision: float
    recall: float
    brier_score: float
    feature_importances: Dict[str, float]
    training_samples: int
    artifact_path: str
    trained_at: str


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------


def _load_or_generate_data(data_dir: str) -> pd.DataFrame:
    """Load adherence data from disk, or generate synthetic if missing."""
    adherence_path = Path(data_dir) / "adherence_events.csv"

    if adherence_path.exists():
        logger.info(f"Loading existing adherence data from {adherence_path}")
        df = pd.read_csv(adherence_path)
    else:
        logger.warning("No training data found — generating synthetic dataset (10k patients, 90 days)")
        from apps.ai_engine.datasets.generator import generate_dataset
        result = generate_dataset(n_patients=10_000, n_days=90, output_dir=data_dir)
        df = result["adherence"]

    return df


def _rebalance_classes(feature_df: pd.DataFrame, max_majority_ratio: float = 3.0) -> pd.DataFrame:
    """
    Downsample the majority label down to `max_majority_ratio` times the
    minority count.

    Real adherence data (and this synthetic generator) skews heavily toward
    non-adherent patients, so the "adherent" class is a thin minority. Fixing
    that purely via XGBoost's scale_pos_weight distorts predict_proba away
    from true likelihoods at extreme ratios (it shifts the loss gradient, not
    the learned probability surface) — undersampling the majority class keeps
    the training distribution closer to natural and gives much better
    calibrated probabilities across the full risk spectrum.
    """
    counts = feature_df["label"].value_counts()
    if len(counts) < 2:
        return feature_df

    minority_label = counts.idxmin()
    majority_label = counts.idxmax()
    minority_count = int(counts[minority_label])
    majority_cap = int(minority_count * max_majority_ratio)

    majority_rows = feature_df[feature_df["label"] == majority_label]
    minority_rows = feature_df[feature_df["label"] == minority_label]

    if len(majority_rows) > majority_cap:
        majority_rows = majority_rows.sample(n=majority_cap, random_state=42)

    balanced = pd.concat([majority_rows, minority_rows]).sample(frac=1, random_state=42)
    logger.info(
        f"Rebalanced classes: {len(minority_rows)} minority / {len(majority_rows)} majority "
        f"(was {counts[majority_label]} majority)"
    )
    return balanced.reset_index(drop=True)


def _prepare_train_test_split(
    feature_df: pd.DataFrame, config: TrainingConfig
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Stratified train/test split preserving class balance."""
    from sklearn.model_selection import train_test_split

    X = feature_df[[c for c in feature_df.columns if c not in ("patient_id", "label")]]
    y = feature_df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=y,
    )
    return X_train, X_test, y_train, y_test


def train_model(
    config: Optional[TrainingConfig] = None,
    data_dir: Optional[str] = None,
    model_dir: Optional[str] = None,
) -> TrainingResult:
    """
    Full training pipeline:
    1. Load data
    2. Engineer features
    3. Train XGBoost
    4. Evaluate (AUC, F1, Brier)
    5. Compute SHAP feature importances
    6. Save artifact
    7. Return TrainingResult
    """
    try:
        import xgboost as xgb
        from sklearn.calibration import calibration_curve
        from sklearn.metrics import (
            brier_score_loss,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
    except ImportError as e:
        raise ImportError(
            f"Missing ML dependencies: {e}\n"
            "Run: pip install xgboost scikit-learn shap"
        )

    if config is None:
        config = TrainingConfig()
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR
    if model_dir is None:
        model_dir = DEFAULT_MODEL_DIR

    os.makedirs(model_dir, exist_ok=True)
    logger.info(f"Training model v{config.model_version}")

    # 1. Load data
    adherence_df = _load_or_generate_data(data_dir)

    # 2. Feature engineering
    from apps.ai_engine.services.feature_engineering import build_training_features
    feature_df = build_training_features(adherence_df)
    feature_df = feature_df.dropna()

    logger.info(f"Training set: {len(feature_df):,} patients, {feature_df['label'].mean():.1%} non-adherent")

    # Undersample the (heavily dominant) non-adherent class so the model
    # trains on a naturally balanced distribution — see _rebalance_classes.
    feature_df = _rebalance_classes(feature_df)
    logger.info(f"Balanced set: {len(feature_df):,} patients, {feature_df['label'].mean():.1%} non-adherent")

    # 3. Split
    X_train, X_test, y_train, y_test = _prepare_train_test_split(feature_df, config)

    # 4. Train — scale_pos_weight left near 1.0 since class balance is now
    # handled by resampling above, not loss reweighting (which distorts
    # predict_proba away from true likelihoods at extreme ratios).
    model = xgb.XGBClassifier(
        n_estimators=config.n_estimators,
        max_depth=config.max_depth,
        learning_rate=config.learning_rate,
        subsample=config.subsample,
        colsample_bytree=config.colsample_bytree,
        scale_pos_weight=1.0,
        random_state=config.random_state,
        eval_metric=config.eval_metric,
        early_stopping_rounds=config.early_stopping_rounds,
        verbosity=0,
    )

    # Validation set for early stopping
    from sklearn.model_selection import train_test_split as tts
    X_tr, X_val, y_tr, y_val = tts(
        X_train, y_train, test_size=0.15, random_state=config.random_state, stratify=y_train
    )
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # 5. Evaluate
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    auc = roc_auc_score(y_test, y_prob)
    f1 = f1_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    brier = brier_score_loss(y_test, y_prob)

    logger.info(
        f"Evaluation | AUC={auc:.4f} F1={f1:.4f} Precision={prec:.4f} Recall={rec:.4f} Brier={brier:.4f}"
    )

    # 6. Feature importances (via XGBoost gain)
    importance_dict = {k: float(v) for k, v in zip(X_train.columns, model.feature_importances_)}
    importance_sorted = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

    # 7. Save artifact
    artifact_path = Path(model_dir) / f"{config.model_name}_v{config.model_version}.pkl"
    metadata_path = Path(model_dir) / f"{config.model_name}_v{config.model_version}_meta.json"

    with open(artifact_path, "wb") as f:
        pickle.dump(
            {
                "model": model,
                "feature_names": list(X_train.columns),
                "config": asdict(config),
                "trained_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
        )

    result = TrainingResult(
        model_version=config.model_version,
        auc_roc=round(auc, 4),
        f1_score=round(f1, 4),
        precision=round(prec, 4),
        recall=round(rec, 4),
        brier_score=round(brier, 4),
        feature_importances=importance_sorted,
        training_samples=len(X_train),
        artifact_path=str(artifact_path),
        trained_at=datetime.now(timezone.utc).isoformat(),
    )

    with open(metadata_path, "w") as f:
        json.dump(asdict(result), f, indent=2)

    logger.info(f"Model saved: {artifact_path}")

    # 8. Register in DB (if Django is available)
    _register_model_in_db(config, result, str(artifact_path))

    return result


def _register_model_in_db(
    config: TrainingConfig,
    result: TrainingResult,
    artifact_path: str,
) -> None:
    """Register model in ai_engine.model_registry. Safe no-op if DB unavailable."""
    try:
        import django
        django.setup()
    except Exception:
        pass

    try:
        from apps.ai_engine.models import AIModelRegistry

        AIModelRegistry.objects.filter(model_name=config.model_name, is_active=True).update(
            is_active=False
        )
        AIModelRegistry.objects.create(
            model_name=config.model_name,
            model_version=config.model_version,
            algorithm_type="XGBoost",
            is_active=True,
            auc_roc=result.auc_roc,
            f1_score=result.f1_score,
            precision_score=result.precision,
            recall_score=result.recall,
            brier_score=result.brier_score,
            training_dataset_size=result.training_samples,
            training_cutoff_date=date.today(),
            feature_list=list(result.feature_importances.keys()),
            hyperparameters={
                "n_estimators": config.n_estimators,
                "max_depth": config.max_depth,
                "learning_rate": config.learning_rate,
            },
            artifact_path=artifact_path,
            deployed_at=datetime.now(timezone.utc),
        )
        logger.info(f"Model v{config.model_version} registered in DB as active")
    except Exception as e:
        logger.warning(f"Could not register model in DB (OK during standalone training): {e}")


# ---------------------------------------------------------------------------
# Load saved model
# ---------------------------------------------------------------------------


def load_model(version: Optional[str] = None, model_dir: Optional[str] = None) -> dict:
    """
    Load a trained model artifact from disk.
    If version is None, loads the latest available.

    Returns dict: {model, feature_names, config, trained_at}
    """
    if model_dir is None:
        model_dir = DEFAULT_MODEL_DIR

    model_path = Path(model_dir)

    if version:
        artifact = model_path / f"adherence_risk_xgb_v{version}.pkl"
    else:
        # Find latest
        candidates = list(model_path.glob("adherence_risk_xgb_v*.pkl"))
        if not candidates:
            raise FileNotFoundError(f"No model artifacts found in {model_dir}")
        artifact = max(candidates, key=lambda p: p.stat().st_mtime)

    with open(artifact, "rb") as f:
        payload = pickle.load(f)

    logger.info(f"Model loaded: {artifact}")
    return payload


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    version = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"
    cfg = TrainingConfig(model_version=version)
    result = train_model(config=cfg)

    print("\n=== Training Complete ===")
    print(json.dumps(asdict(result), indent=2))
