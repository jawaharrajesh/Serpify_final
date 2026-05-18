import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re

# --- TOOL META ---
INFO = {
    "title": "Self-Link Finder",
    "icon": "🔄",
    "description": "Detect redundant internal links where a page points to its own URL."
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Self-Link Finder",
    layout="wide"
)

# --- SESSION ---
def create_session():

    s = requests.Session()

    retries = Retry(
        total=1,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )

    adapter = HTTPAdapter(
        pool_connections=20,
        pool_maxsize=20,
        max_retries=retries
    )

    s.mount("https://", adapter)
    s.mount("http://", adapter)

    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        )
    })

    s.verify = False

    return s

SESSION = create_session()

# --- HELPERS ---
def classify_link(a):

    if a.find_parent("nav"):
        return "Navigation"

    if a.find_parent("footer"):
        return "Footer"

    if "btn" in " ".join(a.get("class", [])).lower():
        return "CTA Button"

    return "Body/Inline"

def is_self_link(source_url, target_url):

    return source_url.rstrip("/") == target_url.rstrip("/")

# --- IGNORE BREADCRUMB / NAVIGATION LINKS ---
def should_ignore_link(a):

    # Ignore breadcrumb components
    if a.find_parent(attrs={"data-testid": re.compile("breadcrumb", re.I)}):
        return True

    # Ignore navigation structures
    if a.find_parent("nav"):
        return True

    # Ignore breadcrumb/menu/tab classes
    classes = " ".join(a.get("class", [])).lower()

    ignore_keywords = [
        "breadcrumb",
        "tab",
        "menu",
        "navigation",
        "nav"
    ]

    if any(k in classes for k in ignore_keywords):
        return True

    return False

# --- CORE SCAN ---
def audit_self_links(url):

    results = []

    try:

        r = SESSION.get(
            url,
            timeout=20
        )

        if r.status_code != 200:
            return results

        soup = BeautifulSoup(r.text, "lxml")

        for a in soup.find_all("a", href=True):

            # Ignore breadcrumb/navigation links
            if should_ignore_link(a):
                continue

            href = a["href"]

            # Ignore anchors and JS links
            if href.startswith("#") or "javascript:" in href:
                continue

            full_link = urljoin(url, href)

            # SELF LINK CHECK
            if is_self_link(url, full_link):

                results.append({
                    "Source Page": url,
                    "Self-Link URL": full_link,
                    "Element Type": classify_link(a),
                    "Anchor Text": (
                        a.get_text(strip=True)[:50]
                        or "[Image/Icon]"
                    )
                })

    except:
        pass

    return results

# --- FETCH SITEMAP URLS ---
def fetch_sitemap_urls(sm_url):

    urls = set()

    try:

        r = SESSION.get(
            sm_url,
            timeout=20
        )

        locs = re.findall(
            r'<loc>(https?://[^<]+)</loc>',
            r.text
        )

        for loc in locs:

            loc = loc.strip()

            # Nested sitemap support
            if loc.endswith(".xml"):

                nested = fetch_sitemap_urls(loc)

                urls.update(nested)

            else:
                urls.add(loc)

    except:
        pass

    return list(urls)

# --- UI ---
def render():

    st.header("🔄 Self-Link Finder")

    st.markdown(
        "Identify redundant internal links that point "
        "back to the same page."
    )

    sitemap_input = st.text_input(
        "Sitemap URL",
        placeholder="https://www.example.com/sitemap.xml"
    )

    if st.button("🚀 Run Full Audit", use_container_width=True):

        if not sitemap_input:

            st.error("Please provide a sitemap URL.")

            return

        with st.status("🔍 Scanning pages...", expanded=True) as status:

            urls = fetch_sitemap_urls(sitemap_input)

            if not urls:

                status.update(
                    label="❌ No URLs found in sitemap.",
                    state="error"
                )

                return

            total = len(urls)

            st.write(f"🚀 Auditing {total} pages...")

            MAX_WORKERS = 10

            progress = st.progress(0)

            findings = []

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

                futures = {
                    executor.submit(audit_self_links, u): u
                    for u in urls
                }

                for i, f in enumerate(as_completed(futures)):

                    try:

                        res = f.result()

                        if res:
                            findings.extend(res)

                    except:
                        pass

                    progress.progress(
                        min((i + 1) / total, 1.0)
                    )

            # --- RESULTS ---
            if findings:

                status.update(
                    label=f"✅ Scan Complete: {len(findings)} Self-Links Found",
                    state="complete"
                )

                df = pd.DataFrame(findings)

                st.warning("⚠️ Redundant Self-Links Detected")

                st.dataframe(
                    df,
                    use_container_width=True
                )

                csv = df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    "📩 Download Report",
                    csv,
                    "self_links.csv",
                    "text/csv"
                )

            else:

                status.update(
                    label="✅ Scan Complete: No Issues",
                    state="complete"
                )

                st.success("🎉 No self-links found!")

# --- RUN APP ---
if __name__ == "__main__":
    render()
