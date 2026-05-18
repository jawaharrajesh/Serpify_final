import streamlit as st
import pandas as pd
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.utils import get_sitemap_urls, find_pdfs_on_page, search_keyword_in_pdf

INFO = {
    "title": "PDF Keyword Scanner",
    "icon": "📄",
    "description": "Scan all PDFs across a sitemap for a specific keyword."
}

def run_pdf_scan(sitemap_url, keyword, max_workers=10):
    # ── PHASE 1: Get all page URLs from sitemap ──────────────────
    status_text = st.empty()
    progress_bar = st.progress(0, text="Fetching sitemap URLs...")

    status_text.markdown("🗺️ **Phase 1/3** — Reading sitemap...")
    page_urls = get_sitemap_urls(sitemap_url)
    total_pages = len(page_urls)

    if total_pages == 0:
        st.error("No URLs found in sitemap. Check the URL and try again.")
        st.stop()

    status_text.markdown(f"🗺️ **Phase 1/3** — Found **{total_pages}** pages in sitemap")

    # ── PHASE 2: Find PDFs on each page ──────────────────────────
    all_pdfs = {}
    lock = threading.Lock()
    completed_pages = 0

    progress_bar.progress(0, text=f"Phase 2/3 — Crawling pages for PDF links (0/{total_pages})")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(find_pdfs_on_page, url): url for url in page_urls}
        for future in as_completed(futures):
            source_url = futures[future]
            completed_pages += 1
            try:
                pdfs = future.result()
            except Exception:
                pdfs = []

            if pdfs:
                with lock:
                    for pdf in pdfs:
                        all_pdfs[pdf] = source_url

            pct = int((completed_pages / total_pages) * 50)  # 0–50%
            progress_bar.progress(
                pct,
                text=f"🔗 Phase 2/3 — Crawling pages ({completed_pages}/{total_pages}) | {len(all_pdfs)} PDFs found so far"
            )

    total_pdfs = len(all_pdfs)
    status_text.markdown(f"🔗 **Phase 2/3** — Found **{total_pdfs}** PDFs across {total_pages} pages")

    if total_pdfs == 0:
        progress_bar.progress(100, text="Complete — No PDFs found")
        return [], []

    # ── PHASE 3: Search keyword in each PDF ──────────────────────
    results = []
    flagged = []
    completed_pdfs = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(search_keyword_in_pdf, pdf_url, keyword): (pdf_url, src)
            for pdf_url, src in all_pdfs.items()
        }
        for future in as_completed(futures):
            pdf_url, src = futures[future]
            completed_pdfs += 1
            try:
                res = future.result()
            except Exception:
                continue

            res["source_page"] = src
            results.append(res)
            if res.get("flagged"):
                flagged.append(res)

            pct = 50 + int((completed_pdfs / total_pdfs) * 50)  # 50–100%
            progress_bar.progress(
                pct,
                text=f"📄 Phase 3/3 — Scanning PDFs ({completed_pdfs}/{total_pdfs}) | {len(flagged)} flagged so far"
            )

    progress_bar.progress(100, text=f"✅ Complete — {total_pdfs} PDFs scanned, {len(flagged)} flagged")
    status_text.markdown(f"📄 **Phase 3/3** — Scanned **{total_pdfs}** PDFs | **{len(flagged)}** flagged for `{keyword}`")

    return results, flagged


# ── UI ────────────────────────────────────────────────────────────────
st.markdown("""
<div class='tool-header'>
    <div class='tool-title'>📄 PDF Keyword Scanner</div>
    <p style='color:#666; margin:0;'>Scan every PDF linked across your sitemap for a keyword.</p>
</div>
""", unsafe_allow_html=True)

col_a, col_b = st.columns([3, 1])
with col_a:
    sitemap_url = st.text_input(
        "Enter Website or Sitemap URL",
        placeholder="https://example.com or https://example.com/sitemap.xml"
    )
with col_b:
    keyword = st.text_input("Keyword to Search", value="1993")

# Optional: limit pages to scan for speed
with st.expander("⚙️ Advanced Options"):
    max_workers = st.slider("Parallel workers (higher = faster but heavier)", 5, 30, 10)
    max_pages = st.number_input("Max pages to crawl (0 = unlimited)", min_value=0, value=0, step=50)

if st.button("🔍 Run PDF Scan", use_container_width=True):
    if not sitemap_url:
        st.error("Please enter a website or sitemap URL.")
        st.stop()

    if not sitemap_url.endswith(".xml"):
        sitemap_url = sitemap_url.rstrip("/") + "/sitemap.xml"

    try:
        results, flagged = run_pdf_scan(sitemap_url, keyword, max_workers=max_workers)
    except Exception as e:
        st.error(f"Scan failed: {e}")
        st.stop()

    if not results:
        st.warning("No PDFs were found across the sitemap.")
        st.stop()

    st.success(f"✅ {len(results)} PDFs scanned — {len(flagged)} flagged for keyword **'{keyword}'**")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total PDFs Found", len(results))
    c2.metric("Flagged PDFs", len(flagged))
    c3.metric("Clean PDFs", len(results) - len(flagged))

    if flagged:
        st.subheader("🚨 Flagged PDFs")
        st.dataframe(pd.DataFrame(flagged), use_container_width=True)

    st.subheader("📋 All Results")
    st.dataframe(pd.DataFrame(results), use_container_width=True)

    csv = pd.DataFrame(results).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Full Report (CSV)", csv, "pdf_scan_results.csv", "text/csv")
