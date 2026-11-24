import numpy as np
import pandas as pd

from data import generate_dataset
from database import repository as repo
from models import features, predictor, trainer


def test_synthetic_flagged_missing_values_and_insert_retrieve(new_student):
    s = repo.list_students()
    assert s[s.is_synthetic == 1].shape[0] >= 100 and s[s.username == new_student["username"]].is_synthetic.iloc[0] == 0
    assert s[["sleep_hours", "attendance_pct", "prior_gpa"]].isna().any().any()  # missingness present
    sid = new_student["student_id"]
    repo.add_quiz(sid, 1, repo.get_topics(1).topic_id.iloc[0], 42, 50, "2025-01-05", 12)
    q = repo.get_quizzes(sid)
    assert len(q) == 1 and abs(q.score_pct.iloc[0] - 84.0) < 1e-9


def test_models_trained_with_real_metrics():
    m = trainer.load_metrics()
    assert m and predictor.models_available()
    assert 0 < m["regression"]["mae"] < 15 and -1 <= m["regression"]["r2"] <= 1
    assert m["classification"]["accuracy"] > m["classification"]["baseline_majority_accuracy"]
    assert sum(sum(r) for r in m["classification"]["confusion_matrix"]) == m["data"]["test_rows"]
    assert m["segmentation"]["k"] in (3, 4, 5)


def test_predictions_in_range_and_persisted():
    predictor.refresh()
    p = repo.get_performance()
    assert p.predicted_score.dropna().between(0, 100).all() and p.predicted_category.dropna().isin(["At Risk", "Average", "Good", "Excellent"]).all()
    assert repo.list_students().segment.notna().sum() >= 100


def test_no_target_leakage_in_features():
    q, a = repo.get_quizzes(), repo.get_activities()
    st = repo.list_students().rename(columns={"student_id": "id"})
    base = features.build_subject_features(q, a, st, mode="train")
    q2, a2 = q.copy(), a.copy()
    cutoffs, late_ids = {}, []
    for (sid, subj), g in q2.groupby(["student_id", "subject"]):
        g = g.sort_values(["quiz_date", "id"])
        n = len(g)
        if n < 5:
            continue
        k = min(max(3, int(np.ceil(0.7 * n))), n - 1)
        cutoffs[(sid, subj)] = g.quiz_date.iloc[k - 1]
        late_ids += g.id.iloc[k:].tolist()
    q2.loc[q2.id.isin(late_ids), "score_pct"] = 0.0           # destroy every LATER quiz score
    key = pd.Series(list(zip(a2.student_id, a2.subject)))
    cut = key.map(cutoffs)
    after = (a2.activity_date.values > pd.to_datetime(cut).values) & cut.notna().values
    a2.loc[after, "duration_min"] = 99999.0                    # and every LATER activity
    mod = features.build_subject_features(q2, a2, st, mode="train")
    pd.testing.assert_frame_equal(base[features.NUM_FEATURES].reset_index(drop=True), mod[features.NUM_FEATURES].reset_index(drop=True))
    assert not np.allclose(base.target_score, mod.target_score)  # target did change, features did not
