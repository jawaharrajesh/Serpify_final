import streamlit as st
import requests
import pandas as pd
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="404 Link Hunter", layout="wide")

# ---------------- SESSION SETUP ----------------
def create_session():
    s = requests.Session()

    # Retry only once
    retries = Retry(
        total=1,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )

    adapter = HTTPAdapter(
        pool_connections=50,
        pool_maxsize=50,
        max_retries=retries
    )

    s.mount("https://", adapter)
    s.mount("http://", adapter)

    s.headers.update({
        "User-Agent": "Mozilla/5.0"
    })

    s.verify = False

    return s

SESSION = create_session()

# ---------------- FETCH SITEMAP URLS ----------------
def fetch_all_sitemap_urls(sitemap_url):
    urls = set()

    try:
        r = SESSION.get(sitemap_url, timeout=20)

        locs = re.findall(r"<loc>(.*?)</loc>", r.text)

        for loc in locs:
            loc = loc.strip()

            if loc.endswith(".xml"):
                urls.update(fetch_all_sitemap_urls(loc))
            else:
                urls.add(loc)

    except Exception:
        pass

    return urls

# ---------------- CHECK ONLY 404 URLS ----------------
def check_url_fast(url):

    try:
        # Use GET instead of HEAD to avoid false timeout/blocking
        r = SESSION.get(
            url,
            timeout=10,
            allow_redirects=True,
            stream=True
        )

        status = r.status_code

        r.close()

        # ONLY RETURN 404 PAGES
        if status == 404:
            return {
                "URL": url,
                "Status": "404 Not Found"
            }

        return None

    except requests.exceptions.Timeout:

        # Retry one more time manually
        try:
            r = SESSION.get(
                url,
                timeout=10,
                allow_redirects=True,
                stream=True
            )

            status = r.status_code

            r.close()

            if status == 404:
                return {
                    "URL": url,
                    "Status": "404 Not Found"
                }

        except:
            return None

    except:
        return None

# ---------------- STREAMLIT UI ----------------
def render():

    st.title("🚫 404 Link Hunter")
    st.markdown("Scan sitemap and detect only 404 pages.")

    sitemap_input = st.text_input(
        "Enter Sitemap URL",
        placeholder="https://example.com/sitemap.xml"
    )

    max_workers = st.slider(
        "Threads",
        5,
        50,
        20
    )

    if st.button("🚀 Start Scan", use_container_width=True):

        if not sitemap_input:
            st.error("Please enter sitemap URL")
            return

        with st.status("Fetching sitemap URLs...", expanded=True):

            urls = fetch_all_sitemap_urls(sitemap_input)

            if not urls:
                st.error("No URLs found")
                return

            urls = list(urls)

            st.write(f"✅ Total URLs Found: {len(urls)}")

            broken_links = []

            progress = st.progress(0)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:

                futures = {
                    executor.submit(check_url_fast, url): url
                    for url in urls
                }

                for i, f in enumerate(as_completed(futures)):

                    res = f.result()

                    if res:
                        broken_links.append(res)

                    progress.progress((i + 1) / len(urls))

        # ---------------- RESULTS ----------------
        if broken_links:

            df = pd.DataFrame(broken_links)

            st.error(f"❌ {len(df)} 404 Pages Found")

            st.dataframe(df, use_container_width=True)

            st.download_button(
                "📩 Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                "404_report.csv",
                "text/csv"
            )

        else:
            st.success("🎉 No 404 pages found!")

# ---------------- RUN ----------------
if __name__ == "__main__":
    render()
