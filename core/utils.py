import requests
import re
import fitz  # PyMuPDF
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

# ─── EXISTING FUNCTIONS (unchanged) ──────────────────────────────────

def is_garbage_link(url):
    IGNORE_KEYWORDS = ["icon", "logo", "font", "sprite", "badge", "btn", "button",
                       "mstile", "android", "apple", "favicon", "manifest",
                       "loader", "spinner", ".svg"]
    url_lower = url.lower()
    if url_lower.startswith("data:"):
        return True
    for kw in IGNORE_KEYWORDS:
        if kw in url_lower:
            return True
    return False

def check_asset_health(url, session):
    try:
        r = session.head(url, timeout=10, allow_redirects=True)
        if r.status_code == 404:
            return True, "404 NOT FOUND"
        if r.status_code >= 400:
            return True, f"STATUS {r.status_code}"
        return False, "OK"
    except:
        return False, "TIMEOUT/ERROR"

def get_image_details(img_url, session):
    try:
        res = session.head(img_url, timeout=5)
        size_bytes = int(res.headers.get('Content-Length', 0))
        size_kb = size_bytes / 1024
        dim_match = re.search(r'(\d{2,4})x(\d{2,4})', img_url)
        res_str = f"{dim_match.group(1)}x{dim_match.group(2)}" if dim_match else "Unknown"
        return size_kb, res_str
    except:
        return 0, "N/A"


# ─── NEW: PDF SCANNER FUNCTIONS ───────────────────────────────────────

def get_sitemap_urls(sitemap_url: str) -> list[str]:
    """
    Fetches all page URLs from an XML sitemap.
    Handles sitemap index files (nested sitemaps) automatically.
    """
    urls = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Serpify SEO Bot)"}
        res = requests.get(sitemap_url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "xml")

        # Sitemap index — contains links to other sitemaps
        sitemap_tags = soup.find_all("sitemap")
        if sitemap_tags:
            for sitemap in sitemap_tags:
                loc = sitemap.find("loc")
                if loc:
                    child_urls = get_sitemap_urls(loc.text.strip())
                    urls.extend(child_urls)
        else:
            # Regular sitemap — contains page URLs
            for loc in soup.find_all("loc"):
                urls.append(loc.text.strip())

    except Exception as e:
        print(f"[get_sitemap_urls] Error fetching {sitemap_url}: {e}")

    return urls


def find_pdfs_on_page(page_url: str) -> list[str]:
    """
    Scrapes a page and returns all absolute PDF URLs found in <a> tags.
    """
    pdf_links = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Serpify SEO Bot)"}
        res = requests.get(page_url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            # Resolve relative URLs to absolute
            absolute = urljoin(page_url, href)
            if absolute.lower().endswith(".pdf"):
                pdf_links.append(absolute)

    except Exception as e:
        print(f"[find_pdfs_on_page] Error on {page_url}: {e}")

    return list(set(pdf_links))  # deduplicate


def search_keyword_in_pdf(pdf_url: str, keyword: str) -> dict:
    """
    Downloads a PDF and searches for a keyword across all pages.
    Returns a result dict with match info.
    """
    result = {
        "pdf_url": pdf_url,
        "keyword": keyword,
        "flagged": False,
        "match_count": 0,
        "matched_pages": [],
        "preview": "",
        "error": None
    }

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Serpify SEO Bot)"}
        res = requests.get(pdf_url, headers=headers, timeout=20, stream=True)
        res.raise_for_status()

        # Load PDF from bytes using PyMuPDF
        pdf_bytes = res.content
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        keyword_lower = keyword.lower()
        previews = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if keyword_lower in text.lower():
                result["flagged"] = True
                result["match_count"] += 1
                result["matched_pages"].append(page_num + 1)

                # Grab a small snippet around the keyword for preview
                idx = text.lower().find(keyword_lower)
                start = max(0, idx - 60)
                end = min(len(text), idx + 60)
                snippet = text[start:end].replace("\n", " ").strip()
                previews.append(f"p{page_num + 1}: ...{snippet}...")

        result["matched_pages"] = ", ".join(map(str, result["matched_pages"]))
        result["preview"] = " | ".join(previews[:3])  # show up to 3 snippets
        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result
