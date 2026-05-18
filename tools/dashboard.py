import streamlit as st
import pandas as pd
from analytics.db import get_conn

def render():
    st.markdown("""
    <div class="tool-header">
        <div class="tool-icon">📊</div>
        <div>
            <div class="tool-title">Analytics Dashboard</div>
            <div class="tool-sub">Overview of all your audit activity</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    user_id = st.session_state.get("user_id", "admin")
    conn = get_conn()

    try:
        df = pd.read_sql_query(
            "SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC",
            conn, params=(user_id,)
        )
    except Exception as e:
        st.info("Analytics will appear once you run your first tool!")
        conn.close()
        return
    finally:
        conn.close()

    if df.empty:
        st.info("No audit history yet. Run your first tool from the sidebar!")
        return

    total     = len(df)
    completed = len(df[df["status"] == "completed"])
    failed    = len(df[df["status"] == "failed"])
    rate      = (completed / total * 100) if total > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Jobs",    total)
    m2.metric("Completed",     completed)
    m3.metric("Failed",        failed)
    m4.metric("Success Rate",  f"{rate:.1f}%")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Tool Usage")
        st.bar_chart(df["tool"].value_counts())
    with c2:
        st.subheader("Status Breakdown")
        st.bar_chart(df["status"].value_counts())

    st.subheader("Recent Jobs")
    st.dataframe(
        df[["job_id", "tool", "status", "created_at"]].head(20),
        use_container_width=True,
        hide_index=True
    )

render()
