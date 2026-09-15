# Implementation Plan: Dynamic & Accurate AI Risk Scoring Across Patients

Fix the root causes resulting in a static 81% (`0.8070`) risk score across all patient accounts, and enable personalized, dynamic risk scores (e.g., 5%–20% for adherent patients, 40%–60% for moderate, 80%+ for high-risk missed dose patients).

---

## Technical Root Cause Summary

1. **Schema Mismatches in Data Fetching (`risk_engine.py`):**
   - `Prescription.objects.filter(status="active")` throws `FieldError` because the field is `is_active=True`.
   - `_calculate_age(date_of_birth)` throws `TypeError` when DOB is `None`.
   - `compute_timing_features(events)` throws `KeyError: 'status'` when events DataFrame is empty.
   - *Impact:* Every patient's data extraction crashed and fell back to `FEATURE_DEFAULTS`.

2. **Rolling Window Date Discrepancy:**
   - The database demo dataset contains ReminderJobs from June 2026.
   - The AI engine calculates rolling 7-day and 30-day windows relative to `datetime.now(timezone.utc)` (September 2026).
   - Because no doses were scheduled within the last 7 days of September, the 7-day window had 0 events for every patient, defaulting to 100% adherence and 0 misses.

3. **Smoke Model Baseline Calibration:**
   - The active model `adherence_risk_xgb_vsmoke-api-celery-3.pkl` was trained with `scale_pos_weight: 2.0` on a small smoke dataset.
   - Its baseline leaf output for zero recent misses is **0.8070** (81%).

4. **Frontend Session Cache:**
   - `useRiskScore('me')` caches under `['ai', 'risk', 'me']`. When logging out and switching patients in the same tab without a hard reload, React Query served the cached score.

---

## User Review Required

> [!IMPORTANT]
> **Scoring Mode Behavior:**
> For patients with **no dose history at all** (e.g. brand-new registered users), their initial score should represent a baseline low/neutral risk (e.g., **10%–15% Low Risk**) with the label *"Baseline / New Patient — No dose history recorded yet"* rather than 81% Critical.
>
> For patients with **heavy missed doses** (such as Apollo Indore Patient with 380 missed doses), the score will dynamically evaluate to **85%–95% Critical Risk**.
>
> For patients with **good adherence**, the score will reflect **5%–25% Low Risk**.

---

## Proposed Changes

### Backend Components

#### [MODIFY] [risk_engine.py](file:///c:/aarogyam/Aarogyam-Final/backend/apps/ai_engine/services/risk_engine.py)
- **Fix Prescription Query:** Replace `status="active"` with `is_active=True, deleted_at__isnull=True`. Safely extract daily doses from `p.schedules.count()`.
- **Fix Safe Age Calculation:** Add `if not date_of_birth: return 45` in `_calculate_age`.
- **Adaptive As-Of Timestamp:** When a patient has historical dose records in the DB but none in the last 7 calendar days, set `as_of` to the most recent event's `scheduled_at` (or current time if recent events exist). This ensures historical test data accurately reflects actual adherence performance.
- **Dynamic Risk Score Formulation:** Ensure `RiskEngine.get_risk_score()` leverages calibrated score calculation so low-miss patients receive low scores (5–20%), moderate receive 35–55%, and severe miss patients receive 80–95%.

#### [MODIFY] [feature_engineering.py](file:///c:/aarogyam/Aarogyam-Final/backend/apps/ai_engine/services/feature_engineering.py)
- **Empty DataFrame Guard:** Add safety check in `compute_timing_features`:
  ```python
  if events.empty or "status" not in events.columns:
      return {
          "avg_delay_minutes": FEATURE_DEFAULTS["avg_delay_minutes"],
          "max_delay_minutes": FEATURE_DEFAULTS["max_delay_minutes"],
          "pct_on_time_7d": FEATURE_DEFAULTS["pct_on_time_7d"],
      }
  ```
- **Historical Reference Handling:** In `build_training_features`, use `patient_events["scheduled_at"].max()` as the reference `as_of` date instead of `now()`.

#### [MODIFY] [views.py](file:///c:/aarogyam/Aarogyam-Final/backend/apps/ai_engine/api/views.py)
- **Ensure Patient Resolution:** In `RiskScoreView.get()`, resolve `patient_id == "me"` to `request.user.patient_profile.id` directly if not already resolved, guaranteeing patient-specific DB queries.
- **Force Fresh Calculation Query Param:** Support `?refresh=true` to invalidate cached `PatientRiskScore` rows on demand.

---

### Frontend Components

#### [MODIFY] [Home.jsx](file:///c:/aarogyam/Aarogyam-Final/frontend/src/pages/patient/Home.jsx)
- Pass explicit patient ID to `useRiskScore`:
  ```javascript
  const patientId = user?.patient_id || user?.id || 'me';
  const { data: riskData, isLoading: isRiskLoading } = useRiskScore(patientId);
  const { data: insightsData } = useInsights(patientId);
  ```
- This ensures React Query automatically uses unique cache keys per patient (`['ai', 'risk', patientId]`), preventing stale cross-account cache contamination.

#### [MODIFY] [auth.store.js](file:///c:/aarogyam/Aarogyam-Final/frontend/src/stores/auth.store.js)
- Clear/invalidate React Query cache on `logout()` to guarantee a clean slate for the next login.

---

## Verification Plan

### Automated Tests
1. Run Python test script verifying risk score outputs across 4 distinct patient archetypes:
   - Apollo Indore Patient (380 missed doses): Expected **80%–95% (Critical)**
   - Good Adherence Profile (100% adherence, 0 misses): Expected **5%–20% (Low)**
   - Moderate Miss Profile (2 misses): Expected **30%–50% (Medium)**
   - New Patient Profile (0 dose records): Expected **5%–15% (Low/Neutral Baseline)**
2. Run `py -3.10 manage.py check` to verify backend integrity.
3. Run `npm run build` to ensure frontend builds with 0 errors.

### Manual Verification
- In the browser, log in as `patient+apollo-indore@medadhere.test` and verify RiskMeter shows Critical (~85–90%).
- Log in as a patient with no misses or new account and verify RiskMeter shows Low (~10–15%).
- Verify SHAP reasons and AI Insights reflect the individual patient's real history.
