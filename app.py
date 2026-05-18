"""
app.py — Serpify Main Entry Point
===================================
Run with: streamlit run app.py
"""

import os
import logging
import streamlit as st

from config import settings
from auth.utils import verify_user, bootstrap_admin
from analytics.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title=f"{settings.app.NAME} | SEO Intelligence",
    page_icon="🟣",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS — Serpify Purple Theme ────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&family=Syne:wght@700;800&family=Space+Mono&display=swap');

:root {
    --sp-purple:    #7C3AED;
    --sp-purple-dk: #5B21B6;
    --sp-purple-lt: #F0EBFF;
    --sp-bg:        #FAFAFA;
    --sp-text:      #1E1B4B;
    --sp-border:    #E9E3FF;
    --white:        #FFFFFF;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background-color: var(--sp-bg) !important;
    color: var(--sp-text) !important;
}

[data-testid="stHeader"] { background: transparent !important; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E1B4B 0%, #312E81 100%) !important;
    border-right: none !important;
}

[data-testid="stSidebar"] * { color: #E0E7FF !important; }

[data-testid="stSidebarNavLink"] { border-radius: 8px !important; margin: 2px 0 !important; }
[data-testid="stSidebarNavLink"]:hover { background: rgba(124,58,237,0.3) !important; }
[data-testid="stSidebarNavLink"][aria-selected="true"] { background: rgba(124,58,237,0.5) !important; }

.logo-text {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 1.6rem;
    color: #A78BFA;
    letter-spacing: -0.02em;
}

.tool-header {
    background: linear-gradient(135deg, #7C3AED 0%, #5B21B6 100%);
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    color: white;
    display: flex;
    align-items: center;
    gap: 1rem;
}

.tool-icon { font-size: 2rem; }

.tool-title {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 1.6rem;
    color: white;
}

.tool-sub { color: rgba(255,255,255,0.8); font-size: 0.9rem; margin-top: 2px; }

div.stButton > button {
    background: linear-gradient(135deg, #7C3AED, #5B21B6) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}

div.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(124,58,237,0.4) !important;
}

.stTextInput input { border-radius: 8px !important; border-color: var(--sp-border) !important; }

[data-testid="stMetric"] {
    background: var(--white) !important;
    border: 1px solid var(--sp-border) !important;
    border-radius: 10px !important;
    padding: 1rem !important;
}

[data-testid="stMetricValue"] {
    color: var(--sp-purple) !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 800 !important;
}

.stDataFrame { border-radius: 10px !important; overflow: hidden !important; }
.stExpander { border: 1px solid var(--sp-border) !important; border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)


# ── Startup ───────────────────────────────────────────────────
def startup():
    for d in ["results", "temp"]:
        os.makedirs(d, exist_ok=True)
    init_db()
    bootstrap_admin()


try:
    startup()
except EnvironmentError as e:
    st.error(str(e))
    st.code("cp .env.example .env\n# Then fill in all values")
    st.stop()


# ── Auth Gate ────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_id = None

if not st.session_state.authenticated:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.write(""); st.write("")
        st.markdown("""
        <div style="text-align:center; margin-bottom:2rem">
            <div style="font-size:3rem">🟣</div>
            <h1 style="
                background: linear-gradient(135deg, #7C3AED, #5B21B6);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2.5rem; font-weight: 800; margin: 0.5rem 0 0.25rem;
                font-family: 'Syne', sans-serif;
            ">Serpify</h1>
            <p style="color:#6B7280; margin:0">SEO Intelligence Platform</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        if submitted:
            if verify_user(username, password):
                st.session_state.authenticated = True
                st.session_state.user_id = username
                st.rerun()
            else:
                st.error("Invalid username or password.")

        st.markdown(
            "<p style='text-align:center;color:#9CA3AF;font-size:0.8rem;margin-top:1rem'>"
            "Serpify — Your SEO Intelligence Suite</p>",
            unsafe_allow_html=True
        )
    st.stop()


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:1rem 0 0.5rem">
        <div style="font-size:1.4rem;font-weight:800;color:#A78BFA;font-family:'Syne',sans-serif;letter-spacing:-0.02em">
            🟣 Serpify
        </div>
        <div style="font-size:0.75rem;color:#A5B4FC;margin-top:2px">SEO Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    user_id = st.session_state.get("user_id", "")
    st.markdown(f"""
    <div style="background:rgba(124,58,237,0.2);border-radius:8px;padding:0.5rem 0.75rem;
                margin-bottom:0.5rem;font-size:0.85rem;color:#C7D2FE">
        👤 {user_id}
    </div>
    """, unsafe_allow_html=True)

    if st.button("Sign Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.rerun()

    st.markdown("<hr style='border-color:#4338CA;margin:0.75rem 0'>", unsafe_allow_html=True)


# ── Page Routing ─────────────────────────────────────────────
home_page    = st.Page("tools/home.py",        title="Dashboard",   icon="🏠", default=True)
history_page = st.Page("tools/job_history.py", title="Job History", icon="📜")

# Auto-discover all tools
icon_map = {
    "ai_audit.py":            "🧠",
    "broken_link_finder.py":  "🚫",
    "bulk_url_opener.py":     "🚀",
    "dashboard.py":           "📊",
    "ghost_scanner.py":       "👻",
    "keyword_finder.py":      "🔍",
    "meta_audit.py":          "🔎",
    "pdf_extractor.py":       "📄",
    "redirect_loop_finder.py":"🔄",
    "self_link_finder.py":    "🔗",
    "sitemap.py":             "🗺️",
    "zx_ww_scanner.py":       "🎯",
}

seo_tools = []
exclude   = {"home.py", "job_history.py", "__init__.py"}

if os.path.exists("tools"):
    for f in sorted(os.listdir("tools")):
        if f.endswith(".py") and f not in exclude:
            name = f.replace(".py", "").replace("_", " ").title()
            seo_tools.append(
                st.Page(
                    os.path.join("tools", f),
                    title=name,
                    icon=icon_map.get(f, "🛠️"),
                )
            )

pg = st.navigation({
    "Main":      [home_page, history_page],
    "SEO Tools": seo_tools,
})

pg.run()
