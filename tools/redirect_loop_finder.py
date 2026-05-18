import streamlit as st
import requests
import pandas as pd
import re
import urllib3
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Redirect Loop Finder",
    layout="wide"
)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------- CONFIG ----------------
TIMEOUT = 20
MAX_WORKERS = 10
MAX_REDIRECTS = 10

# ---------------- SESSION ----------------
def create_session():

    s = requests.Session()

    retries = Retry(
        total=1,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )

    adapter = HTTPAdapter(
        pool_connections=MAX_WORKERS,
        pool_maxsize=MAX_WORKERS,
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

# ---------------- FETCH SITEMAP ----------------
def fetch_sitemap_urls(sitemap_url):

    urls = set()

    try:

        r = SESSION.get(
            sitemap_url,
            timeout=TIMEOUT
        )

        locs = re.findall(
            r"<loc>(https?://[^<]+)</loc>",
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

# ---------------- REDIRECT CHECKER ----------------
def trace_redirects(url):

    try:

        current_url = url

        visited = []

        chain = []

        for _ in range(MAX_REDIRECTS):

            # LOOP DETECTED
            if current_url in visited:

                chain.append(current_url)

                return {
                    "URL": url,
                    "Final URL": current_url,
                    "Status": "LOOP",
                    "Redirect Chain": " -> ".join(chain)
                }

            visited.append(current_url)

            r = SESSION.get(
                current_url,
                timeout=TIMEOUT,
                allow_redirects=False
            )

            status = r.status_code

            chain.append(f"{current_url} [{status}]")

            # REDIRECT
            if status in [301, 302, 307, 308]:

                location = r.headers.get("Location")

                if not location:
                    break

                next_url = urljoin(current_url, location)

                current_url = next_url

            # 404
            elif status == 404:

                return {
                    "URL": url,
                    "Final URL": current_url,
                    "Status": 404,
                    "Redirect Chain": " -> ".join(chain)
                }

            # FINAL SUCCESS
            else:

                # Only report problematic URLs
                if len(chain) > 1:

                    return {
                        "URL": url,
                        "Final URL": current_url,
                        "Status": status,
                        "Redirect Chain": " -> ".join(chain)
                    }

                return None

        # TOO MANY REDIRECTS
        return {
            "URL": url,
            "Final URL": current_url,
            "Status": "TOO MANY REDIRECTS",
            "Redirect Chain": " -> ".join(chain)
        }

    except requests.exceptions.TooManyRedirects:

        return {
            "URL": url,
            "Final URL": current_url,
            "Status": "LOOP",
            "Redirect Chain": "Too many redirects"
        }

    except Exception as e:

        return {
            "URL": url,
            "Final URL": "",
            "Status": "ERROR",
            "Redirect Chain": str(e)
        }

# ---------------- UI ----------------
def render():

    st.markdown("""
    <div class="tool-header">
        <div class="tool-icon">🔄</div>
        <div>
            <div class="tool-title">Redirect Loop Finder</div>
            <div class="tool-sub">
                Detect redirect chains, infinite loops, and 404 pages
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    sitemap_url = st.text_input(
        "Sitemap XML URL",
        placeholder="https://example.com/sitemap.xml"
    )

    path_filter = st.text_input(
        "Sub-folder filter (optional)",
        placeholder="/products/"
    )

    if st.button(
        "🚀 Start Redirect Audit",
        use_container_width=True
    ):

        if not sitemap_url:

            st.error("Please provide a sitemap URL.")

            return

        with st.status(
            "🔍 Scanning Redirects...",
            expanded=True
        ) as status:

            st.write("Fetching sitemap URLs...")

            urls = fetch_sitemap_urls(sitemap_url)

            if not urls:

                status.update(
                    label="❌ No URLs found in sitemap",
                    state="error"
                )

                return

            # FILTER PATH
            if path_filter:

                urls = [
                    u for u in urls
                    if path_filter in u
                ]

            total = len(urls)

            st.write(f"🚀 Auditing {total} URLs...")

            findings = []

            progress = st.progress(0)

            with ThreadPoolExecutor(
                max_workers=MAX_WORKERS
            ) as executor:

                futures = {
                    executor.submit(trace_redirects, u): u
                    for u in urls
                }

                for i, f in enumerate(as_completed(futures)):

                    try:

                        res = f.result()

                        if res:
                            findings.append(res)

                    except:
                        pass

                    progress.progress(
                        (i + 1) / total
                    )

            # ---------------- RESULTS ----------------
            if findings:

                df = pd.DataFrame(findings)

                redirects = df[
                    df["Status"].isin(
                        [301, 302, 307, 308]
                    )
                ]

                loops = df[
                    df["Status"] == "LOOP"
                ]

                dead = df[
                    df["Status"] == 404
                ]

                st.success("✅ Redirect Audit Complete")

                m1, m2, m3, m4 = st.columns(4)

                m1.metric("Total Issues", len(df))
                m2.metric("Redirects", len(redirects))
                m3.metric("Loops", len(loops))
                m4.metric("404 Pages", len(dead))

                st.markdown("### 📋 Redirect Findings")

                st.dataframe(
                    df,
                    use_container_width=True
                )

                st.download_button(
                    "📩 Download Report",
                    df.to_csv(index=False).encode("utf-8"),
                    "redirect_audit.csv",
                    "text/csv"
                )

            else:

                st.success(
                    "🎉 No redirect issues detected!"
                )

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    render()
