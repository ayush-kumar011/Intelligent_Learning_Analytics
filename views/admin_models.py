import pandas as pd
import streamlit as st
from sklearn.decomposition import PCA

from config import settings
from database import repository as repo
from models import predictor, trainer
from models.features import SEG_FEATURES, build_student_features
from utils import charts
from utils.ui import plot, require_role


def render():
    require_role("admin")
    st.title("Model Lab")
    st.caption("All numbers below are computed on a held-out set of students (split by student to avoid leakage). Nothing is hard-coded.")
    c = st.columns(2)
    if c[0].button("Retrain models (and refresh all predictions)", type="primary"):
        with st.spinner("Training Random Forests and K-Means..."):
            trainer.train_all()
            n = predictor.refresh()
        st.success(f"Models retrained; predictions refreshed for {n} students.")
    if c[1].button("Refresh predictions only"):
        with st.spinner("Scoring students..."):
            st.success(f"Updated {predictor.refresh()} students.")
    m = trainer.load_metrics()
    if not m:
        st.warning("No trained models found.")
        return
    d, r, k, s = m["data"], m["regression"], m["classification"], m["segmentation"]
    st.markdown(f"**Trained:** {m['trained_at']} &nbsp;|&nbsp; **Rows:** {d['rows']} student-subject pairs from {d['students']} students "
                f"(train {d['train_rows']}, test {d['test_rows']} from {d['test_students']} unseen students) &nbsp;|&nbsp; "
                f"**Synthetic share of students:** {d['synthetic_student_share']:.0%}")
    st.caption(f"Target: {d['target']}.")
    t1, t2, t3 = st.tabs(["Performance prediction", "Category classification", "Student segmentation"])
    with t1:
        st.markdown("**Purpose:** estimate each student's upcoming quiz average per subject so support can start early.")
        a = st.columns(4)
        a[0].metric("MAE (points)", f"{r['mae']:.2f}")
        a[1].metric("RMSE", f"{r['rmse']:.2f}")
        a[2].metric("R2", f"{r['r2']:.3f}")
        a[3].metric("Naive baseline MAE", f"{r['baseline_mae_early_avg']:.2f}", help="Predicting the student's own earlier average")
        gain = (r["baseline_mae_early_avg"] - r["mae"]) / r["baseline_mae_early_avg"] * 100
        st.info(f"5-fold grouped CV MAE: {r['cv_mae_mean']:.2f} +/- {r['cv_mae_std']:.2f}. Improvement over the naive baseline: {gain:.1f}%. "
                "The model is dominated by the student's earlier average; extra features add a modest gain.")
        plot(charts.feature_importance_fig(m["feature_importance"]))
    with t2:
        st.markdown("**Purpose:** classify the expected performance category (At Risk < 50, Average < 70, Good < 85, Excellent).")
        a = st.columns(3)
        a[0].metric("Accuracy", f"{k['accuracy']:.1%}")
        a[1].metric("Macro F1", f"{k['f1_macro']:.3f}")
        a[2].metric("Majority-class baseline", f"{k['baseline_majority_accuracy']:.1%}")
        plot(charts.confusion_matrix_fig(k["confusion_matrix"], k["labels"]))
        rep = pd.DataFrame(k["report"]).T.loc[k["labels"], ["precision", "recall", "f1-score", "support"]].round(3)
        st.dataframe(rep)
    with t3:
        st.markdown("**Purpose:** group students by learning behaviour (scores, consistency, study time, completion) to tailor support.")
        sil = s["silhouette_by_k"]
        st.write(f"K-Means with k={s['k']} chosen from k in {{3,4,5}} by silhouette ({', '.join(f'k={a}: {b:.3f}' for a, b in sil.items())}). "
                 "A silhouette around 0.2-0.3 means segments are a sensible partition of a continuum, not sharply separated clusters.")
        quizzes, acts = repo.get_quizzes(), repo.get_activities()
        sf = build_student_features(quizzes, acts)
        if len(sf):
            seg = predictor.assign_segments(sf)
            art = predictor._load("seg")
            pts = PCA(2, random_state=settings.RANDOM_STATE).fit_transform(art["pipeline"][:-1].transform(sf[SEG_FEATURES]))
            df = sf.merge(seg, on="student_id").assign(PC1=pts[:, 0], PC2=pts[:, 1])
            plot(charts.segment_scatter(df))
            st.dataframe(df.groupby("segment")[SEG_FEATURES].mean().round(2).assign(students=df.groupby("segment").size()))
