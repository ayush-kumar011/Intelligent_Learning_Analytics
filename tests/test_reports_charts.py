from analytics import metrics
from utils import charts, reports


def test_report_exports():
    d = reports.report_data(1)
    pdf = reports.student_pdf(d)
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000
    for fn in (reports.subjects_csv, reports.topics_csv, reports.recommendations_csv):
        assert b"," in fn(d)
    assert b"subject" in reports.subjects_csv(d)


def test_charts_build_from_database_data():
    sp = metrics.subject_performance(1)
    figs = [charts.subject_bar(sp), charts.score_timeline(metrics.score_timeline(1)), charts.weekly_time(metrics.weekly_time(1)),
            charts.topic_heatmap(metrics.topic_mastery(1)), charts.cohort_hist(metrics.score_distribution()),
            charts.cohort_trend(metrics.cohort_trend()), charts.subject_cohort_bar(metrics.cohort_subject_stats())]
    assert all(len(f.data) > 0 for f in figs)
    assert abs(sum(figs[0].data[0].y) / len(figs[0].data[0].y) - sp.avg_score.mean()) < 1e-6  # chart values come from DB
