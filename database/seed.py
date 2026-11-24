"""Seeds reference data: subjects, topics and a seed catalogue of learning materials."""
from config.curriculum import CURRICULUM, LEVELS, MATERIAL_TYPES
from database import db

_MINUTES = {"Video Lecture": 20, "Reading": 25, "Practice Set": 35}
_LEVEL_MULT = {"Beginner": 1.0, "Intermediate": 1.2, "Advanced": 1.5}


def seed_reference_data() -> None:
    if db.scalar("SELECT COUNT(*) FROM subjects"):
        return
    with db.get_conn() as conn:
        for subject, topics in CURRICULUM.items():
            sid = conn.execute("INSERT INTO subjects(name) VALUES (?)", (subject,)).lastrowid
            for topic, diff in topics:
                tid = conn.execute(
                    "INSERT INTO topics(subject_id, name, difficulty) VALUES (?,?,?)", (sid, topic, diff)
                ).lastrowid
                for level, mtype in zip(LEVELS, MATERIAL_TYPES):
                    conn.execute(
                        "INSERT INTO materials(topic_id,title,material_type,level,url,est_minutes,description) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (tid, f"{topic}: {level} {mtype}", mtype, level, None,
                         int(_MINUTES[mtype] * _LEVEL_MULT[level]),
                         "Seed catalogue entry (no external link). Admins can add real resources."),
                    )
