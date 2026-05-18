import streamlit as st
import time
import json
import os
import pandas as pd
from urllib.parse import urlparse

from jobs.job_manager import start_job, get_job
from core.scraper import build_sitemap_script

def render():
    if "jobs" not in st.session_state:
        st.session_state["jobs"] = {}

    st.markdown("""
    <div class="tool-header">
        <div class="tool-icon">🗺️</div>
        <div>
            <div class="tool-title">Sitemap Auditor</div>
            <div class="tool-sub">Compare live pages vs XML sitemap · Find orphans & coverage gaps</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("sm_form"):
        sitemap_url = st.text_input("Sitemap XML URL", placeholder="https://example.com/sitemap.xml")
        exclude_paths = st.text_area("Paths to exclude (comma-separated)", placeholder="/search?, #, /api/")
        submitted = st.form_submit_button("🚀 Start Sitemap Audit")

    if submitted and "sitemap" not in st.session_state["jobs"]:
        if not sitemap_url:
            st.error("Please provide a Sitemap URL.")
            return

        user_id = st.session_state.get("user_id", "admin")
        params = {"sitemap_url": sitemap_url, "exclude_paths": exclude_paths}
        
        def builder(output_path):
            return build_sitemap_script(sitemap_url, output_path)

        job_id = start_job(user_id, "sitemap", params, builder)
        st.session_state["jobs"]["sitemap"] = job_id
        st.rerun()

    if "sitemap" in st.session_state["jobs"]:
        job_id = st.session_state["jobs"]["sitemap"]
        job = get_job(job_id)
        
        if job:
            status = job[3]
            result_path = job[5]
            st.caption(f"**Job ID:** `{job_id}`")

            if status in ["queued", "running"]:
                with st.spinner(f"⏳ Auditing Sitemap ({status.upper()})..."):
                    time.sleep(2)
                    st.rerun()
            
            elif status == "failed":
                st.error(f"❌ Job failed: {job[7]}")
                if st.button("Start New Audit"):
                    st.session_state["jobs"].pop("sitemap", None)
                    st.rerun()

            elif status == "completed":
                if not result_path or not os.path.exists(result_path):
                    st.error("Result file missing.")
                    return

                try:
                    with open(result_path, "r") as f:
                        data = json.load(f)
                except:
                    st.error("Invalid result file.")
                    return
                
                # Data Processing
                df_live = pd.DataFrame(data.get("live", []), columns=["URL"])
                df_official = pd.DataFrame(data.get("sitemap", []), columns=["URL"]).drop_duplicates()
                
                # Filtering logic
                if exclude_paths:
                    excl_list = [p.strip() for p in exclude_paths.split(',') if p.strip()]
                    for excl in excl_list:
                        df_live = df_live[~df_live["URL"].str.contains(excl, regex=False, na=False)]
                        df_official = df_official[~df_official["URL"].str.contains(excl, regex=False, na=False)]

                missing_in_xml = df_live[~df_live["URL"].isin(df_official["URL"])]
                orphans = df_official[~df_official["URL"].isin(df_live["URL"])]

                st.success("✅ Audit Complete!")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Live Pages", len(df_live))
                m2.metric("Sitemap Entries", len(df_official))
                m3.metric("Missing from XML", len(missing_in_xml), delta_color="inverse")
                m4.metric("Orphan Pages", len(orphans), delta_color="inverse")

                tab1, tab2, tab3 = st.tabs(["⚠️ Missing from XML", "👻 Orphans", "🌐 All Data"])
                with tab1:
                    st.dataframe(missing_in_xml, use_container_width=True)
                with tab2:
                    st.dataframe(orphans, use_container_width=True)
                with tab3:
                    st.write("**Live Crawl Data:**")
                    st.dataframe(df_live, use_container_width=True)
                    st.write("**Official XML Data:**")
                    st.dataframe(df_official, use_container_width=True)

                col_dl, col_new = st.columns([1, 4])
                with col_dl:
                    st.download_button("⬇️ Download JSON", data=json.dumps(data, indent=2), file_name=f"sitemap_audit_{job_id}.json")
                with col_new:
                    if st.button("Start New Audit"):
                        st.session_state["jobs"].pop("sitemap", None)
                        st.rerun()

if __name__ == "__main__":
    render()