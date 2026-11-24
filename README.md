# Intelligent Learning Analytics for Personalized Educational Recommendations

Streamlit + SQLite + scikit-learn system that analyses quiz results and learning activity, predicts upcoming
performance, segments learners, finds learning gaps and generates personalised recommendations.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
First launch creates the database, seeds a **synthetic** cohort (300 students) and trains the models (~30 s).
Afterwards start-up is instant and all data persists in `data/learning_analytics.db`.

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `Admin@12345` (override with env `LA_ADMIN_PASSWORD`) |
| Demo student (synthetic data) | `demo_student` | `Student@123` |
| Real student | register on the login page | your choice |

Optional CLI: `python -m data.generate_dataset --export-csv` (seed DB + CSV copies in `data/synthetic/`),
`python -m models.trainer` (retrain, prints metrics), `python -m pytest -q` (tests).

## Architecture
```
app.py                  auth gate, role-based st.navigation
config/                 settings (paths, thresholds), curriculum (6 subjects x 6 topics)
database/               db.py (schema, connections) | repository.py (all SQL) | seed.py
services/               auth.py (PBKDF2-SHA256 + salt, validation) | bootstrap.py (first-run setup)
data/generate_dataset.py  synthetic cohort generator (is_synthetic=1) and DB seeding
models/                 features.py | trainer.py (train+evaluate+save) | predictor.py (inference -> DB)
analytics/metrics.py    topic mastery, subject stats, cohort analytics
recommendations/engine.py  data-driven recommendations
utils/                  charts (Plotly), reports (CSV + PDF via ReportLab/Matplotlib), ui, validation
pages/                  student: dashboard, recommendations, log learning, profile, reports
                        admin: overview, students, model lab, materials, reports
tests/                  35 tests (DB, auth, data, ML, leakage, recommendations, reports, UI)
```
Flow: log quiz/activity -> `repository` -> `predictor.refresh` (features -> RF models + K-Means -> `student_performance`,
`student_insights`) -> `engine.generate` -> `recommendations` table -> dashboards/reports.

**Tables:** users, students, subjects, topics, materials, learning_activities, quiz_results, student_performance,
student_insights, recommendations (foreign keys + CHECK constraints enforced).

## Machine learning (what each model is for)
* **Performance prediction (RandomForestRegressor)** - predicts a student's *upcoming* quiz average per subject. Label =
  mean of the last ~30% of that student's quizzes in the subject; features come only from the earlier ~70% of quizzes and
  activities (verified by `test_no_target_leakage_in_features`). Train/test split is by student (GroupShuffleSplit).
* **Category classification (RandomForestClassifier)** - At Risk (<50), Average (<70), Good (<85), Excellent.
* **Segmentation (K-Means)** - groups students on score level, consistency, trend, weekly study minutes, active-day ratio,
  completion, quiz frequency. k chosen from {3,4,5} by silhouette; segments named from centroids.
* **Learning gaps / recommendations** - *not* ML: recency-weighted topic mastery (30-day half-life) vs. the 70% target and
  vs. peers; spaced-repetition intervals (1/3/7/14 days by mastery); level-matched materials; difficulty adapts to mastery
  and trend; model outputs (projection, segment, risk) add subject alerts and engagement advice.
* Missing values: median imputation inside the sklearn pipeline (fit on training rows only); ~3-5% of profile fields are
  deliberately missing in the synthetic data.

### Measured results (this repo, seed 42, 300 synthetic students, 331 held-out rows from 60 unseen students)
| Task | Result | Naive baseline |
|---|---|---|
| Score regression | MAE 5.80 pts, RMSE 7.23, R2 0.806 (grouped 5-fold CV MAE 5.92 +/- 0.30) | MAE 6.11 (predict own earlier average) |
| Category classification | accuracy 67.7%, macro-F1 0.685 | majority class 39.9% |
| K-Means | k=3, silhouette 0.248 | - |

Reproduce with `python -m models.trainer`; the Model Lab page shows live metrics, confusion matrix and feature importance.

## Limitations (please read)
* **The cohort is synthetic.** Metrics show the pipeline works and recovers the generator's structure; they say nothing
  about accuracy on real students. Retrain on real institutional data before drawing conclusions.
* The regressor beats "predict the student's own earlier average" by only ~5%; most signal is past performance.
  Silhouette 0.25 means segments partition a continuum rather than reveal sharply separated groups.
* Seeded learning materials are placeholder titles with no links; admins add real ones on the Materials page.
* New real students need >=3 quizzes per subject for projections and >=5 quizzes in total for a segment.
* Security is academic-grade: hashed passwords and per-session login lockout, but no email verification, password
  reset, HTTPS or audit log. Change the default admin password.
* SQLite is single-writer (fine for a demo / small class). Synthetic dates are relative to the day of seeding, so on an old
  database "overdue" revision counts grow; delete `data/learning_analytics.db` and `models/artifacts/` to reseed.
* Verified by automated tests (Streamlit `AppTest`, server health check) - not by manual testing in a browser; no screenshots included.
