import streamlit as st
import json
import pandas as pd
import io
import os
import tempfile
from urllib.parse import urlparse

from core.scraper import build_keyword_script


# ✅ Prevent Excel crash
def df_to_excel_bytes(sheets: dict) -> bytes:
    def safe_df(df):
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
        return pd.DataFrame({"Info": ["No data found for this section."]})

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            safe_df(df).to_excel(writer, sheet_name=name[:31], index=False)
    return buf.getvalue()


def render():
    st.markdown("""
    <div class="tool-header">
        <div class="tool-icon">🔍</div>
        <div>
            <div class="tool-title">Keyword Finder</div>
            <div class="tool-sub">Scan every page for a text match · Background Execution</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # FORM
    with st.form("kw_form"):
        sitemap_url = st.text_input("Sitemap XML URL")
        keyword = st.text_input("Keyword to search for")
        path_filter = st.text_input("Sub-folder filter (optional)")
        submitted = st.form_submit_button("🚀 Start Crawl")

    if submitted:
        if not sitemap_url or not keyword:
            st.error("Please fill in both the Sitemap URL and Keyword.")
            return

        progress_bar = st.progress(0, text="Initialising crawler…")
        status = st.empty()

        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "results.json")

            # ✅ RUN YOUR SCRAPER DIRECTLY (NO JOB SYSTEM)
            progress_bar.progress(20, text="Fetching sitemap...")
            status.info("Scanning pages...")

            build_keyword_script(
                sitemap_url,
                keyword.lower(),
                path_filter,
                output_path
            )

            progress_bar.progress(80, text="Processing results...")

            if not os.path.exists(output_path):
                st.error("No output generated. Please check the sitemap.")
                return

            with open(output_path) as f:
                data = json.load(f)

        # ✅ SAFE DATA HANDLING
        results_data = data.get("results", [])
        sitemap_data = data.get("sitemap", [])

        df_all = pd.DataFrame(results_data) if results_data else pd.DataFrame(columns=["URL", "Status", "Keyword_Found"])
        df_official = pd.DataFrame(sitemap_data, columns=["URL"]) if sitemap_data else pd.DataFrame(columns=["URL"])

        # ✅ LOGIC FROM YOUR ORIGINAL WORKING VERSION
        keyword_hits = df_all[df_all["Keyword_Found"] == True] if not df_all.empty else pd.DataFrame()

        missing_in_xml = df_all[
            (df_all["Status"] == 200) &
            (~df_all["URL"].isin(df_official["URL"]))
        ] if not df_all.empty else pd.DataFrame()

        orphans = df_official[
            ~df_official["URL"].isin(df_all["URL"])
        ] if not df_official.empty else pd.DataFrame()

        progress_bar.progress(100, text="Done!")
        status.success("✅ Crawl complete!")

        # METRICS
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pages Scanned", len(df_all))
        c2.metric("🚩 Keyword Hits", len(keyword_hits))
        c3.metric("Missing from XML", len(missing_in_xml))
        c4.metric("Orphan Pages", len(orphans))

        # ✅ SAFE DISPLAY (FIXED ERROR)
        st.markdown("### 🚩 Keyword Hits")
        if not keyword_hits.empty:
            st.dataframe(keyword_hits, use_container_width=True)
        else:
            st.info("No keyword matches found.")

        with st.expander("📋 All Scanned Pages"):
            if not df_all.empty:
                st.dataframe(df_all, use_container_width=True)
            else:
                st.info("No pages scanned.")

        # EXPORT
        sheets = {
            "1. KEYWORD HITS": keyword_hits,
            "2. Missing from Sitemap": missing_in_xml,
            "3. Orphans (XML Only)": orphans,
            "4. All Live Audit": df_all,
            "5. Official Sitemap List": df_official,
        }

        excel_bytes = df_to_excel_bytes(sheets)

        st.download_button(
            "⬇️ Download Full Excel Report",
            data=excel_bytes,
            file_name=f"Keyword_Audit_{urlparse(sitemap_url).netloc}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    render()
