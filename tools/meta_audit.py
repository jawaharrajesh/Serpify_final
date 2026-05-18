import streamlit as st
import time
import os
import pandas as pd

from jobs.job_manager import start_job, get_job
from core.scraper import build_meta_audit_script

INFO = {
    "title": "Meta Pixel Auditor",
    "icon": "🔍",
    "description": "Audit meta titles & descriptions using pixel + character limits."
}


def render():
    if "jobs" not in st.session_state:
        st.session_state["jobs"] = {}

    st.markdown("""
    <div class="tool-header">
        <div class="tool-icon">🔍</div>
        <div>
            <div class="tool-title">Meta Pixel Auditor</div>
            <div class="tool-sub">Find pages with title & description truncation issues</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---- INPUT ----
    with st.form("meta_form"):
        sitemap_url = st.text_input("Sitemap URL", placeholder="https://example.com/sitemap.xml")
        submitted = st.form_submit_button("🚀 Start Meta Audit")

    # ---- START JOB ----
    if submitted and "meta" not in st.session_state["jobs"]:
        if not sitemap_url:
            st.error("Please provide a Sitemap URL.")
            return

        user_id = st.session_state.get("user_id", "admin")
        params = {"sitemap_url": sitemap_url}

        def builder(output_path):
            return build_meta_audit_script(sitemap_url, output_path)

        job_id = start_job(user_id, "meta", params, builder)
        st.session_state["jobs"]["meta"] = job_id
        st.rerun()

    # ---- JOB STATUS ----
    if "meta" in st.session_state["jobs"]:
        job_id = st.session_state["jobs"]["meta"]
        job = get_job(job_id)

        if job:
            status = job[3]
            result_path = job[5]

            st.caption(f"**Job ID:** `{job_id}`")

            if status in ["queued", "running"]:
                with st.spinner(f"⏳ Auditing ({status.upper()})..."):
                    time.sleep(2)
                    st.rerun()

            elif status == "failed":
                st.error("❌ Job failed")
                st.write(job)

                if st.button("Start New Audit"):
                    st.session_state["jobs"].pop("meta", None)
                    st.rerun()

            elif status == "completed":
                if not result_path or not os.path.exists(result_path):
                    st.error("Result file missing.")
                    return

                excel_path = result_path.replace(".json", ".xlsx")

                if not os.path.exists(excel_path):
                    st.error("Excel report not generated.")
                    return

                df = pd.read_excel(excel_path)

                st.success("✅ Audit Complete!")

                col1, col2 = st.columns(2)
                col1.metric("⚠️ Issue Pages", len(df))
                col2.metric("✔️ Status", "Completed")

                if df.empty:
                    st.success("🎉 No meta issues found!")
                else:
                    st.dataframe(df, use_container_width=True)

                with open(excel_path, "rb") as f:
                    st.download_button(
                        "⬇️ Download Excel Report",
                        data=f,
                        file_name=f"meta_audit_{job_id}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                if st.button("Start New Audit"):
                    st.session_state["jobs"].pop("meta", None)
                    st.rerun()


if __name__ == "__main__":
    render()
