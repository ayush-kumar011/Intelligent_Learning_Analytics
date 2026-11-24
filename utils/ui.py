"""Shared Streamlit helpers: styling, plotting wrappers, role guards."""
import pandas as pd
import streamlit as st

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1250px;}
[data-testid="stMetric"] {background:#F3F4F8; border-radius:12px; padding:12px 16px; border:1px solid #E5E7EB;}
.badge {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem; font-weight:600; color:#fff;}
.b-high{background:#DC2626}.b-med{background:#D97706}.b-low{background:#059669}.b-seg{background:#4F46E5}
.rec-card {border:1px solid #E5E7EB; border-left:5px solid #4F46E5; border-radius:10px; padding:10px 14px; margin-bottom:8px; background:#FAFAFC;}
.rec-p1{border-left-color:#DC2626}.rec-p2{border-left-color:#D97706}.rec-p3{border-left-color:#059669}
.rec-title{font-weight:600} .rec-detail{color:#4B5563; font-size:0.92rem}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def plot(fig, **kw):
    """Version-tolerant st.plotly_chart (width='stretch' on new Streamlit, use_container_width on old)."""
    try:
        st.plotly_chart(fig, width="stretch", **kw)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, **kw)


def table(df: pd.DataFrame, **kw):
    try:
        st.dataframe(df, width="stretch", hide_index=True, **kw)
    except TypeError:
        st.dataframe(df, use_container_width=True, hide_index=True, **kw)


def risk_badge(risk) -> str:
    cls = {"High": "b-high", "Medium": "b-med", "Low": "b-low"}.get(risk, "b-seg")
    return f'<span class="badge {cls}">{risk or "n/a"} risk</span>'


def current_user() -> dict | None:
    return st.session_state.get("user")


def require_role(role: str) -> dict:
    """Page-level authorisation: stops rendering if the session lacks the role."""
    user = current_user()
    if not user or user["role"] != role:
        st.error("You are not authorised to view this page.")
        st.stop()
    return user
