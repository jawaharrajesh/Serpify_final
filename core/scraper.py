import json

# ✅ KEYWORD SEARCH
def build_keyword_script(sitemap_url, search_text, path_filter, out_json):
    sitemap_url = json.dumps(sitemap_url)
    search_text = json.dumps(search_text.lower())
    out_json = out_json.replace("\\", "/")

    return f"""
import requests
import json
import advertools as adv

results = []
sitemap_urls = []

try:
    df = adv.sitemap_to_df({sitemap_url})
    if 'loc' in df.columns:
        sitemap_urls = df['loc'].dropna().tolist()
except Exception as e:
    print(e)

for url in sitemap_urls[:300]:
    try:
        r = requests.get(url, timeout=10)
        text = r.text.lower() if r.status_code == 200 else ""
        results.append({{
            "URL": url,
            "Status": r.status_code,
            "Keyword_Found": {search_text} in text
        }})
    except:
        results.append({{
            "URL": url,
            "Status": "ERROR",
            "Keyword_Found": False
        }})

with open("{out_json}", "w") as f:
    json.dump({{"results": results, "sitemap": sitemap_urls}}, f)
"""

# ✅ REDIRECT CHECK
def build_redirect_script(sitemap_url, path_filter, out_json):
    sitemap_url = json.dumps(sitemap_url)
    out_json = out_json.replace("\\", "/")

    return f"""
import requests
import json
import advertools as adv

results = []

try:
    df = adv.sitemap_to_df({sitemap_url})
    urls = df['loc'].dropna().tolist() if 'loc' in df.columns else []
except:
    urls = []

for url in urls[:200]:
    chain = []
    current = url

    try:
        for _ in range(5):
            r = requests.get(current, allow_redirects=False, timeout=10)
            chain.append(current)

            if r.status_code in [301,302,307,308]:
                nxt = r.headers.get("Location")
                if not nxt or nxt in chain:
                    break
                current = nxt
            else:
                break

        results.append({{
            "URL": url,
            "Final_Dest": current,
            "Status": r.status_code,
            "Chain": " -> ".join(chain)
        }})

    except:
        results.append({{
            "URL": url,
            "Final_Dest": "ERROR",
            "Status": "ERROR",
            "Chain": ""
        }})

with open("{out_json}", "w") as f:
    json.dump({{"results": results}}, f)
"""

# ✅ SITEMAP CHECK
def build_sitemap_script(sitemap_url, out_json):
    sitemap_url = json.dumps(sitemap_url)
    out_json = out_json.replace("\\", "/")

    return f"""
import requests
import json
import advertools as adv

live_urls = []
sitemap_urls = []

try:
    df = adv.sitemap_to_df({sitemap_url})
    if 'loc' in df.columns:
        sitemap_urls = df['loc'].dropna().tolist()
except:
    pass

for url in sitemap_urls[:300]:
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            live_urls.append(url)
    except:
        pass

with open("{out_json}", "w") as f:
    json.dump({{"live": live_urls, "sitemap": sitemap_urls}}, f)
"""
def build_meta_audit_script(sitemap_url, output_path):
    excel_path = output_path.replace(".json", ".xlsx")

    return f"""
import requests
from bs4 import BeautifulSoup
from PIL import ImageFont, ImageDraw, Image
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# -------- CONFIG --------
HEADERS = {{"User-Agent": "Mozilla/5.0"}}
MAX_WORKERS = 15

# -------- GET SITEMAP URLS --------
def get_sitemap_urls(url):
    urls = []

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "xml")

        # Check for nested sitemaps
        sitemaps = soup.find_all("sitemap")
        if sitemaps:
            for sm in sitemaps:
                loc = sm.find("loc").text
                urls.extend(get_sitemap_urls(loc))
        else:
            for u in soup.find_all("url"):
                loc = u.find("loc")
                if loc:
                    urls.append(loc.text)

    except:
        pass

    return urls

# -------- PIXEL WIDTH --------
def get_pixel_width(text):
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        font = ImageFont.load_default()

    img = Image.new("RGB", (1000, 200))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]

# -------- VALIDATION --------
def validate(text, type_):
    if type_ == "title":
        max_px, min_c, max_c = 600, 5, 60
    else:
        max_px, min_c, max_c = 960, 5, 155

    px = get_pixel_width(text)
    length = len(text)

    return {{
        "px": px,
        "len": length,
        "px_status": "OK" if px <= max_px else "Too Long",
        "char_status": "OK" if min_c <= length <= max_c else ("Too Short" if length < min_c else "Too Long")
    }}

# -------- AUDIT SINGLE PAGE --------
def audit_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")

        title = soup.title.string.strip() if soup.title else ""

        desc_tag = soup.find("meta", attrs={{"name": "description"}})
        desc = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""

        t = validate(title, "title")
        d = validate(desc, "description")

        issues = []

        if not title:
            issues.append("Missing Title")
        if not desc:
            issues.append("Missing Description")

        if t["px_status"] != "OK":
            issues.append("Title Pixel Too Long")
        if t["char_status"] != "OK":
            issues.append("Title Char Issue")

        if d["px_status"] != "OK":
            issues.append("Description Pixel Too Long")
        if d["char_status"] != "OK":
            issues.append("Description Char Issue")

        if issues:
            return {{
                "URL": url,
                "Issues": ", ".join(issues),
                "Title": title,
                "Title Length": t["len"],
                "Title Pixels": t["px"],
                "Description": desc,
                "Description Length": d["len"],
                "Description Pixels": d["px"]
            }}

    except:
        return None

    return None

# -------- MAIN --------
urls = get_sitemap_urls("{sitemap_url}")
results = []

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    data = list(executor.map(audit_page, urls))

results = [r for r in data if r]

# -------- SAVE --------
df = pd.DataFrame(results)

if not df.empty:
    df.to_excel("{excel_path}", index=False)

import json
with open("{output_path}", "w") as f:
    json.dump(results, f, indent=2)
"""
