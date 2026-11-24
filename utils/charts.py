"""Plotly figure builders. All inputs are DataFrames derived from database records."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PALETTE = px.colors.qualitative.Set2
_LAYOUT = dict(margin=dict(l=10, r=10, t=40, b=10), template="plotly_white")


def subject_bar(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["avg_score"])
    fig = go.Figure()
    fig.add_bar(x=d.subject, y=d.avg_score, name="Your average", marker_color="#4F46E5")
    if d.cohort_avg.notna().any():
        fig.add_bar(x=d.subject, y=d.cohort_avg, name="Cohort average", marker_color="#9CA3AF")
    if d.predicted_score.notna().any():
        fig.add_bar(x=d.subject, y=d.predicted_score, name="Model projection", marker_color="#10B981")
    fig.add_hline(y=70, line_dash="dot", line_color="#DC2626", annotation_text="Target 70%")
    return fig.update_layout(barmode="group", title="Subject-wise performance", yaxis=dict(range=[0, 100], title="Score (%)"), **_LAYOUT)


def score_timeline(df: pd.DataFrame) -> go.Figure:
    fig = px.line(df, x="week", y="score", color="subject", markers=True, title="Weekly average quiz score by subject",
                  color_discrete_sequence=PALETTE)
    return fig.update_layout(yaxis=dict(range=[0, 100], title="Score (%)"), xaxis_title=None, **_LAYOUT)


def weekly_time(df: pd.DataFrame) -> go.Figure:
    fig = px.bar(df, x="week", y="minutes", color="activity_type", title="Time spent on learning activities (minutes/week)",
                 color_discrete_sequence=PALETTE)
    return fig.update_layout(xaxis_title=None, **_LAYOUT)


def topic_heatmap(df: pd.DataFrame) -> go.Figure:
    groups = [(s, g.sort_values("topic_id")) for s, g in df.groupby("subject")]
    fig = go.Figure(go.Heatmap(
        z=[g["mastery"].tolist() for _, g in groups], y=[s for s, _ in groups],
        x=[f"Topic {i + 1}" for i in range(max(len(g) for _, g in groups))],
        text=[g["topic"].tolist() for _, g in groups], texttemplate="%{text}<br>%{z:.0f}%", colorscale="RdYlGn", zmin=0, zmax=100,
        hovertemplate="%{y} - %{text}: %{z:.0f}%<extra></extra>", colorbar=dict(title="Mastery")))
    return fig.update_layout(title="Topic mastery (blank = not attempted)", height=420, **_LAYOUT)


def cohort_hist(df: pd.DataFrame) -> go.Figure:
    fig = px.histogram(df, x="avg_score", nbins=20, title="Distribution of student average scores", color_discrete_sequence=["#4F46E5"])
    return fig.update_layout(xaxis_title="Average score (%)", yaxis_title="Students", **_LAYOUT)


def cohort_trend(df: pd.DataFrame) -> go.Figure:
    fig = px.line(df, x="week", y="avg_score", markers=True, title="Cohort average quiz score per week", color_discrete_sequence=["#4F46E5"])
    return fig.update_layout(yaxis=dict(range=[0, 100], title="Score (%)"), xaxis_title=None, **_LAYOUT)


def distribution_pie(series: pd.Series, title: str, colors: dict | None = None) -> go.Figure:
    vc = series.fillna("n/a").value_counts().reset_index()
    vc.columns = ["label", "count"]
    fig = px.pie(vc, names="label", values="count", hole=0.45, title=title, color="label",
                 color_discrete_map=colors or {}, color_discrete_sequence=PALETTE)
    return fig.update_layout(**_LAYOUT)


def subject_cohort_bar(df: pd.DataFrame) -> go.Figure:
    fig = px.bar(df, x="avg_score", y="subject", orientation="h", title="Cohort average by subject", color="avg_score",
                 color_continuous_scale="RdYlGn", range_color=[40, 90])
    return fig.update_layout(coloraxis_showscale=False, xaxis_title="Average score (%)", yaxis_title=None, **_LAYOUT)


def confusion_matrix_fig(cm, labels) -> go.Figure:
    fig = px.imshow(np.array(cm), x=labels, y=labels, text_auto=True, color_continuous_scale="Blues",
                    title="Confusion matrix (held-out students)")
    return fig.update_layout(xaxis_title="Predicted", yaxis_title="Actual", **_LAYOUT)


def feature_importance_fig(imp: dict) -> go.Figure:
    s = pd.Series(imp).sort_values()
    s.index = [i.replace("num__", "").replace("cat__subject_", "subject=") for i in s.index]
    fig = px.bar(x=s.values, y=s.index, orientation="h", title="Regressor feature importance (top 15)", color_discrete_sequence=["#4F46E5"])
    return fig.update_layout(xaxis_title="Importance", yaxis_title=None, **_LAYOUT)


def segment_scatter(df: pd.DataFrame) -> go.Figure:
    fig = px.scatter(df, x="PC1", y="PC2", color="segment", hover_data=["avg_score", "minutes_per_week"],
                     title="Student segments (PCA projection of K-Means features)", color_discrete_sequence=PALETTE)
    return fig.update_layout(**_LAYOUT)
