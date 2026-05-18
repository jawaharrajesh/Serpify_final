import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Ghost Image Scanner",
    layout="wide"
)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------- CONFIG ----------------
MAX_THREADS = 10
TIMEOUT = 20

# ---------------- SESSION ----------------
def create_session():

    s = requests.Session()

    retries = Retry(
        total=1,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )

    adapter = HTTPAdapter(
        pool_connections=MAX_THREADS,
        pool_maxsize=MAX_THREADS,
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

# ---------------- FETCH ALL SITEMAP URLS ----------------
def fetch_sitemap_urls(sitemap_url):

    urls = set()

    try:

        r = SESSION.get(
            sitemap_url,
            timeout=TIMEOUT
        )

        locs = re.findall(
            r"<loc>(.*?)</loc>",
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

# ---------------- IMAGE HEALTH CHECK ----------------
def check_image_health(image_url):

    try:

        # Use GET instead of HEAD to reduce false failures
        r = SESSION.get(
            image_url,
            timeout=TIMEOUT,
            stream=True
        )

        status = r.status_code

        r.close()

        # ONLY BROKEN IMAGES
        if status == 404:

            return True, "404 NOT FOUND"

        elif status >= 400:

            return True, f"STATUS {status}"

        content_length = r.headers.get("content-length")

        if content_length:

            try:
                if int(content_length) == 0:
                    return True, "EMPTY FILE"
            except:
                pass

        return False, "OK"

    except requests.exceptions.Timeout:

        # Retry once manually
        try:

            r = SESSION.get(
                image_url,
                timeout=TIMEOUT,
                stream=True
            )

            status = r.status_code

            r.close()

            if status == 404:
                return True, "404 NOT FOUND"

            elif status >= 400:
                return True, f"STATUS {status}"

            return False, "OK"

        except:
            return False, "OK"

    except:
        return False, "OK"

# ---------------- PAGE AUDIT ----------------
def audit_page(page_url, placeholders):

    issues = []

    checked_images = set()

    try:

        r = SESSION.get(
            page_url,
            timeout=TIMEOUT
        )

        if r.status_code != 200:
            return issues

        soup = BeautifulSoup(r.text, "lxml")

        # Syntax check
        if "/.webp" in r.text or "/.jpg" in r.text:

            issues.append({
                "Source Page": page_url,
                "Issue Type": "SYNTAX ERROR",
                "Asset": "Missing Filename"
            })

        # Placeholder keyword check
        page_html = r.text.lower()

        for kw in placeholders:

            if kw.lower() in page_html:

                issues.append({
                    "Source Page": page_url,
                    "Issue Type": "PLACEHOLDER",
                    "Asset": kw
                })

        # Image checks
        for img in soup.find_all("img"):

            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-lazy-src")
            )

            if not src:
                continue

            full_url = urljoin(page_url, src)

            # Avoid duplicate checks
            if full_url in checked_images:
                continue

            checked_images.add(full_url)

            is_broken, reason = check_image_health(full_url)

            if is_broken:

                issues.append({
                    "Source Page": page_url,
                    "Issue Type": "BROKEN IMAGE",
                    "Asset": full_url,
                    "Details": reason
                })

    except:
        pass

    return issues

# ---------------- UI ----------------
def render():

    st.title("👻 Ghost Image Scanner")

    st.markdown(
        "Scan the FULL website sitemap to detect "
        "broken images, placeholders, and syntax issues."
    )

    sitemap_url = st.text_input(
        "Sitemap URL",
        placeholder="https://example.com/sitemap.xml"
    )

    placeholders = st.multiselect(
        "Placeholder Keywords",
        [
            "no-picture-available",
            "nopicture",
            "qc-image",
            "image-image"
        ],
        default=[
            "no-picture-available",
            "nopicture"
        ]
    )

    if st.button(
        "🚀 Start Full Website Scan",
        use_container_width=True
    ):

        if not sitemap_url:

            st.error("Please enter sitemap URL")

            return

        with st.status(
            "🌐 Fetching all pages...",
            expanded=True
        ) as status:

            urls = fetch_sitemap_urls(sitemap_url)

            if not urls:

                status.update(
                    label="❌ No URLs found in sitemap",
                    state="error"
                )

                return

            st.write(f"✅ Total pages found: {len(urls)}")

            all_issues = []

            progress = st.progress(0)

            st.write("🔍 Scanning pages for broken images...")

            with ThreadPoolExecutor(
                max_workers=MAX_THREADS
            ) as executor:

                futures = {
                    executor.submit(
                        audit_page,
                        url,
                        placeholders
                    ): url
                    for url in urls
                }

                for i, f in enumerate(as_completed(futures)):

                    try:

                        result = f.result()

                        if result:
                            all_issues.extend(result)

                    except:
                        pass

                    progress.progress(
                        (i + 1) / len(urls)
                    )

        # ---------------- RESULTS ----------------
        if all_issues:

            df = pd.DataFrame(all_issues)

            st.error(
                f"❌ Found {len(df)} issues"
            )

            st.dataframe(
                df,
                use_container_width=True
            )

            st.download_button(
                "📩 Download Report",
                df.to_csv(index=False).encode("utf-8"),
                f"ghost_report_{int(time.time())}.csv",
                "text/csv"
            )

        else:

            st.success(
                "🎉 No ghost image issues found!"
            )

# ---------------- RUN ----------------
if __name__ == "__main__":
    render()
