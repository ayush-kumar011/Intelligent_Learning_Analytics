from datetime import date

from database import repository as repo
from models import predictor
from recommendations import engine


def test_cold_start_recommendations(new_student):
    recs = engine.generate(new_student["student_id"])
    assert recs and all("diagnostic" in r["title"].lower() or "log" in r["title"].lower() for r in recs)
    assert len(repo.get_recommendations(new_student["student_id"])) == len(recs)


def test_recommendations_use_data_and_differ_between_students():
    a, b = engine.generate(1, persist=False), engine.generate(2, persist=False)
    assert a and b and {r["title"] for r in a} != {r["title"] for r in b}
    assert all(r["detail"] for r in a) and {r["rec_type"] for r in a} >= {"learning_gap", "revision"}


def test_recommendations_adapt_to_new_results(new_student):
    sid = new_student["student_id"]
    topics = repo.get_topics(1)
    weak, strong = int(topics.topic_id.iloc[3]), int(topics.topic_id.iloc[0])
    for _ in range(4):
        repo.add_quiz(sid, 1, weak, 30, 100, date.today(), 10)
        repo.add_quiz(sid, 1, strong, 95, 100, date.today(), 10)
    predictor.refresh([sid])
    recs = engine.generate(sid)
    gap_topics = {r["topic_id"] for r in recs if r["rec_type"] == "learning_gap"}
    assert weak in gap_topics and strong not in gap_topics
    top = [r for r in recs if r["rec_type"] == "learning_gap"][0]
    assert "30%" in top["detail"] or "3" in top["detail"]
    # materials are level-matched: 30% mastery -> Beginner
    assert any("Beginner" in r["detail"] for r in recs if r["rec_type"] == "material")
    # done items are not immediately regenerated
    rid = repo.get_recommendations(sid).query("rec_type == 'learning_gap'").rec_id.iloc[0]
    repo.set_recommendation_status(int(rid), sid, "done")
    assert weak not in {r["topic_id"] for r in engine.generate(sid) if r["rec_type"] == "learning_gap"}
