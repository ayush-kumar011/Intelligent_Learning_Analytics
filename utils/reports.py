"""CSV / PDF report generation for a single student."""
import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from analytics import metrics
from database import repository as repo


def report_data(student_id: int) -> dict:
    student = repo.get_student(student_id)
    sp = metrics.subject_performance(student_id)
    tm = metrics.topic_mastery(student_id)
    return {"student": student, "overview": metrics.student_overview(student_id), "subjects": sp, "topics": tm,
            "weak": tm[(tm.attempts > 0) & (tm.mastery < 70)].sort_values("mastery").head(8),
            "recs": repo.get_recommendations(student_id, "active")}


def subjects_csv(d: dict) -> bytes:
    df = d["subjects"][["subject", "avg_score", "quizzes", "minutes", "cohort_avg", "predicted_score", "predicted_category"]].round(1)
    return df.to_csv(index=False).encode()


def topics_csv(d: dict) -> bytes:
    df = d["topics"][["subject", "topic", "difficulty", "attempts", "mastery", "peer_avg"]].round(1)
    return df.to_csv(index=False).encode()


def recommendations_csv(d: dict) -> bytes:
    return d["recs"][["rec_type", "priority", "title", "detail", "due_date", "subject", "topic"]].to_csv(index=False).encode()


def _chart_png(sp) -> io.BytesIO | None:
    sp = sp.dropna(subset=["avg_score"])
    if sp.empty:
        return None
    fig, ax = plt.subplots(figsize=(7, 3))
    x = range(len(sp))
    ax.bar([i - 0.2 for i in x], sp.avg_score, 0.4, label="You", color="#4F46E5")
    ax.bar([i + 0.2 for i in x], sp.cohort_avg.fillna(0), 0.4, label="Cohort", color="#9CA3AF")
    ax.axhline(70, color="#DC2626", ls=":", lw=1)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sp.subject, rotation=20, fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Score (%)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def _tbl(rows, widths=None):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F4F8")]), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _f(v, fmt="{:.0f}%"):
    return "-" if v is None or v != v else fmt.format(v)


def student_pdf(d: dict) -> bytes:
    st_, ov = d["student"], d["overview"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    ss = getSampleStyleSheet()
    small = ss["BodyText"].clone("small", fontSize=8, leading=10)
    story = [Paragraph("Student Performance Report", ss["Title"]),
             Paragraph(f"<b>{st_['full_name']}</b> | {st_.get('grade_level') or 'n/a'} | generated {date.today():%d %b %Y}"
                       + (" | <i>synthetic demo student</i>" if st_["is_synthetic"] else ""), ss["Normal"]), Spacer(1, 10),
             _tbl([["Average score", "Quizzes", "Study hours", "Completion", "Model projection", "Segment", "Risk"],
                   [_f(ov["avg_score"]), str(ov["quizzes"]), _f(ov["total_hours"], "{:.1f} h"), _f(ov["completion_rate"]),
                    _f(ov["predicted"]), ov["segment"] or "-", ov["risk"] or "-"]]), Spacer(1, 10)]
    png = _chart_png(d["subjects"])
    if png:
        story += [Image(png, width=16 * cm, height=6.9 * cm), Spacer(1, 6)]
    story.append(Paragraph("Subject-wise analytics", ss["Heading2"]))
    rows = [["Subject", "Avg", "Quizzes", "Minutes", "Cohort", "Projected", "Category"]]
    for r in d["subjects"].itertuples():
        rows.append([r.subject, _f(r.avg_score), str(r.quizzes), f"{r.minutes:.0f}", _f(r.cohort_avg), _f(r.predicted_score), r.predicted_category or "-"])
    story += [_tbl(rows), Spacer(1, 8), Paragraph("Weakest topics (mastery below 70%)", ss["Heading2"])]
    if len(d["weak"]):
        story.append(_tbl([["Subject", "Topic", "Mastery", "Attempts", "vs cohort"]] +
                          [[r.subject, r.topic, _f(r.mastery), str(r.attempts), _f(-r.gap_vs_peers, "{:+.0f}")] for r in d["weak"].itertuples()]))
    else:
        story.append(Paragraph("No topics below the 70% target.", ss["Normal"]))
    story += [Spacer(1, 8), Paragraph("Personalised improvement suggestions", ss["Heading2"])]
    recs = d["recs"].head(12)
    if len(recs):
        story.append(_tbl([["Priority", "Suggestion", "Detail"]] + [[str(r.priority), Paragraph(r.title, small), Paragraph(r.detail, small)] for r in recs.itertuples()],
                          [1.5 * cm, 5.5 * cm, 10 * cm]))
    else:
        story.append(Paragraph("No active recommendations. Generate them on the Recommendations page.", ss["Normal"]))
    story += [Spacer(1, 10), Paragraph("Projections are statistical estimates from earlier quiz and activity data, not guarantees.", small)]
    doc.build(story)
    return buf.getvalue()
