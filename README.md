# 🟣 Serpify — SEO Intelligence Platform

> Full-stack SEO SaaS built with Python & Streamlit.
> 12 powerful tools — crawl, audit, scan, and dominate search.

---

## ✨ Tools

| Tool | Description |
|------|-------------|
| 🧠 **AI Audit** | Full AI-powered SEO audit with PageSpeed, keyword density, image audit |
| 🚫 **Broken Link Finder** | Scan your sitemap for all 404 pages using parallel threads |
| 🚀 **Bulk URL Opener** | Open hundreds of URLs in separate browser tabs instantly |
| 📊 **Dashboard** | Analytics overview of all your audit activity |
| 👻 **Ghost Scanner** | Detect broken images and placeholder content across your entire site |
| 🔍 **Keyword Finder** | Crawl every page for a keyword match, find orphans & sitemap gaps |
| 🔎 **Meta Pixel Auditor** | Audit title & description pixel widths for SERP truncation issues |
| 📄 **PDF Keyword Scanner** | Scan all PDFs across a sitemap for a specific keyword |
| 🔄 **Redirect Loop Finder** | Detect redirect chains, infinite loops, and 404 pages |
| 🔗 **Self-Link Finder** | Find pages that redundantly link to themselves |
| 🗺️ **Sitemap Auditor** | Compare live pages vs XML sitemap — find orphans & coverage gaps |
| 🎯 **ZX / WW Auditor** | Deep-scan sitemap for legacy ZX/WW pathing issues |

---

## 🚀 Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/serpify.git
cd serpify

# 2. Virtual environment
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env — fill in ADMIN_PASSWORD and GEMINI_API_KEY

# 5. Run
streamlit run app.py
```

Open http://localhost:8501 and log in with your admin credentials.

---

## ☁️ Deploy to Streamlit Cloud (Free)

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → Create app
3. Set entry point to `app.py`
4. In **Advanced Settings → Secrets**, paste:

```toml
APP_ENV          = "production"
APP_NAME         = "Serpify"
SECRET_KEY       = "your_generated_secret"
DATABASE_URL     = ""
ADMIN_USERNAME   = "admin"
ADMIN_PASSWORD   = "your_strong_password"
GEMINI_API_KEY   = "your_gemini_key"
PAGESPEED_API_KEY = "your_pagespeed_key"
```

5. Click Deploy — live in ~2 minutes ✅

---

## 🗂️ Project Structure

```
serpify/
├── app.py                      ← Entry point
├── config.py                   ← All settings (reads .env)
├── requirements.txt
├── README.md
├── .env.example                ← Template — commit this
├── .env                        ← Your secrets — NEVER commit
├── .gitignore
│
├── analytics/
│   └── db.py                   ← SQLite dev / PostgreSQL prod
│
├── auth/
│   ├── login.py                ← Login UI component
│   └── utils.py                ← bcrypt auth + admin bootstrap
│
├── core/
│   ├── pagespeed.py            ← Google PageSpeed API wrapper
│   ├── scraper.py              ← Script builders for background jobs
│   ├── tool_registry.py        ← Maps tool names → script builders
│   └── utils.py                ← Shared helpers (sitemap, PDF, images)
│
├── jobs/
│   └── job_manager.py          ← Background job runner (threads)
│
└── tools/                      ← Each file = one tool (auto-discovered)
    ├── home.py                 ← Dashboard home
    ├── job_history.py          ← Job history + retry
    ├── ai_audit.py             ← AI-powered full audit
    ├── broken_link_finder.py   ← 404 link scanner
    ├── bulk_url_opener.py      ← Multi-tab URL opener
    ├── dashboard.py            ← Analytics charts
    ├── ghost_scanner.py        ← Broken image detector
    ├── keyword_finder.py       ← Keyword crawler
    ├── meta_audit.py           ← Meta pixel auditor
    ├── pdf_extractor.py        ← PDF keyword scanner
    ├── redirect_loop_finder.py ← Redirect chain detector
    ├── self_link_finder.py     ← Self-link detector
    ├── sitemap.py              ← Sitemap vs live comparator
    └── zx_ww_scanner.py        ← ZX/WW path auditor
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit |
| Language | Python 3.10+ |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | bcrypt |
| Crawling | requests + BeautifulSoup + advertools |
| PDF | PyMuPDF |
| AI | Google Gemini |
| PageSpeed | Google PageSpeed Insights API |
| Background Jobs | Python threading |
| Config | python-dotenv |

---

## 📍 Roadmap

- [ ] Phase 2: Multi-tenancy & user management UI
- [ ] Phase 3: FastAPI backend + React frontend
- [ ] Phase 4: Razorpay/Stripe subscription billing
- [ ] Phase 5: Public launch 🚀
