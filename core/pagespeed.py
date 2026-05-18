import requests

PAGESPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def analyze_pagespeed(url, api_key, strategy="mobile"):

    params = {
        "url": url,
        "key": api_key,
        "strategy": strategy,
        "category": [
            "performance",
            "seo",
            "accessibility",
            "best-practices"
        ]
    }

    try:
        response = requests.get(
            PAGESPEED_ENDPOINT,
            params=params,
            timeout=60
        )

        data = response.json()

        lighthouse = data.get("lighthouseResult", {})
        audits = lighthouse.get("audits", {})
        categories = lighthouse.get("categories", {})

        return {
            "performance_score": int(categories.get("performance", {}).get("score", 0) * 100),
            "seo_score": int(categories.get("seo", {}).get("score", 0) * 100),
            "accessibility_score": int(categories.get("accessibility", {}).get("score", 0) * 100),
            "best_practices_score": int(categories.get("best-practices", {}).get("score", 0) * 100),

            "fcp": audits.get("first-contentful-paint", {}).get("displayValue"),
            "lcp": audits.get("largest-contentful-paint", {}).get("displayValue"),
            "cls": audits.get("cumulative-layout-shift", {}).get("displayValue"),
            "speed_index": audits.get("speed-index", {}).get("displayValue"),
            "tbt": audits.get("total-blocking-time", {}).get("displayValue"),

            "full_data": data
        }

    except Exception as e:
        return {"error": str(e)}
