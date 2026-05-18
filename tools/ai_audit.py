import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from collections import Counter
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.generativeai as genai

# Import helpers
from core.utils import (
    is_garbage_link,
    check_asset_health,
    get_image_details
)

from core.pagespeed import analyze_pagespeed


def render():

    st.title("🧠 Serpify AI Audit")

    # Sidebar
    user_api_key = st.sidebar.text_input(
        "Gemini API Key",
        type="password"
    )

    pagespeed_api_key = st.sidebar.text_input(
        "Google PageSpeed API Key",
        type="password"
    )

    # Inputs
    url_input = st.text_input(
        "Target URL",
        value="https://www.bosch-home.com/za/en/services"
    )

    target_kw = st.text_input(
        "Target Keyword (Optional)"
    )

    if st.button("🚀 START FULL AI AUDIT"):

        session = requests.Session()

        headers = {
            'User-Agent': 'Serpify-Bot/1.0'
        }

        start_time = time.time()

        try:

            with st.spinner("Running audit..."):

                response = session.get(
                    url_input,
                    timeout=15,
                    headers=headers
                )

                latency = time.time() - start_time

                soup = BeautifulSoup(
                    response.text,
                    'html.parser'
                )

                html_content = response.text

                tabs = st.tabs([
                    "📋 Diagnosis",
                    "⚡ PageSpeed",
                    "🧠 AI Strategy",
                    "🔗 Links",
                    "📊 Density",
                    "🖼️ Image & Ghost Audit"
                ])

                # =====================================================
                # 📋 Diagnosis
                # =====================================================

                with tabs[0]:

                    title_str = (
                        soup.title.string.strip()
                        if soup.title
                        else "MISSING"
                    )

                    st.metric(
                        "Server Response",
                        f"{latency:.2f}s"
                    )

                    st.write("Title:", title_str)

                # =====================================================
                # ⚡ PageSpeed Audit
                # =====================================================

                with tabs[1]:

                    st.subheader(
                        "⚡ Google PageSpeed Audit"
                    )

                    if not pagespeed_api_key:

                        st.info(
                            "Enter Google PageSpeed API Key."
                        )

                    else:

                        with st.spinner(
                            "Running PageSpeed Audit..."
                        ):

                            ps_data = analyze_pagespeed(
                                url_input,
                                pagespeed_api_key
                            )

                            if "error" in ps_data:

                                st.error(
                                    ps_data["error"]
                                )

                            else:

                                col1, col2, col3, col4 = st.columns(4)

                                col1.metric(
                                    "Performance",
                                    ps_data['performance_score']
                                )

                                col2.metric(
                                    "SEO",
                                    ps_data['seo_score']
                                )

                                col3.metric(
                                    "Accessibility",
                                    ps_data['accessibility_score']
                                )

                                col4.metric(
                                    "Best Practices",
                                    ps_data['best_practices_score']
                                )

                                st.divider()

                                metric_df = pd.DataFrame([
                                    ["FCP", ps_data["fcp"]],
                                    ["LCP", ps_data["lcp"]],
                                    ["CLS", ps_data["cls"]],
                                    ["Speed Index", ps_data["speed_index"]],
                                    ["TBT", ps_data["tbt"]],
                                ], columns=["Metric", "Value"])

                                st.dataframe(
                                    metric_df,
                                    use_container_width=True
                                )

                                # AI Recommendations
                                if user_api_key:

                                    genai.configure(
                                        api_key=user_api_key
                                    )

                                    model = genai.GenerativeModel(
                                        "gemini-3-flash-preview"
                                    )

                                    perf_prompt = f"""
                                    Analyze these Core Web Vitals:

                                    Performance Score: {ps_data['performance_score']}
                                    LCP: {ps_data['lcp']}
                                    CLS: {ps_data['cls']}
                                    TBT: {ps_data['tbt']}

                                    Provide:
                                    - SEO impact
                                    - UX issues
                                    - Performance fixes
                                    - Developer recommendations
                                    """

                                    try:

                                        ai_perf = model.generate_content(
                                            perf_prompt
                                        )

                                        st.subheader(
                                            "🧠 AI Performance Recommendations"
                                        )

                                        st.write(
                                            ai_perf.text
                                        )

                                    except Exception as e:

                                        st.error(
                                            f"AI Error: {e}"
                                        )

                # =====================================================
                # 🧠 AI Strategy
                # =====================================================

                with tabs[2]:

                    if not user_api_key:

                        st.info(
                            "Enter API key to enable AI."
                        )

                    else:

                        genai.configure(
                            api_key=user_api_key
                        )

                        model = genai.GenerativeModel(
                            "gemini-3-flash-preview"
                        )

                        prompt = f"""
                        Analyze SEO for {url_input}
                        and suggest improvements.
                        """

                        try:

                            res = model.generate_content(
                                prompt
                            )

                            st.write(res.text)

                        except Exception as e:

                            st.error(
                                f"AI Error: {e}"
                            )

                # =====================================================
                # 🔗 Links
                # =====================================================

                with tabs[3]:

                    links = [
                        urljoin(
                            url_input,
                            a.get('href', '')
                        )

                        for a in soup.find_all('a')

                        if a.get('href')
                        and not is_garbage_link(
                            a.get('href')
                        )
                    ]

                    unique_links = list(
                        dict.fromkeys(links)
                    )[:20]

                    broken = []

                    with ThreadPoolExecutor(
                        max_workers=5
                    ) as ex:

                        futures = {
                            ex.submit(
                                check_asset_health,
                                url,
                                session
                            ): url

                            for url in unique_links
                        }

                        for f in as_completed(futures):

                            try:

                                is_err, res = f.result()

                                if is_err:

                                    broken.append({
                                        "URL": futures[f],
                                        "Error": res
                                    })

                            except Exception as e:

                                broken.append({
                                    "URL": futures[f],
                                    "Error": str(e)
                                })

                    df_broken = pd.DataFrame(
                        broken
                    )

                    if df_broken.empty:

                        st.success(
                            "No broken links found."
                        )

                    else:

                        st.dataframe(
                            df_broken
                        )

                # =====================================================
                # 📊 Keyword Density
                # =====================================================

                with tabs[4]:

                    st.subheader(
                        "📊 Keyword Density Analysis"
                    )

                    for s in soup([
                        "script",
                        "style",
                        "nav",
                        "footer"
                    ]):
                        s.extract()

                    words = re.findall(
                        r'\\b\\w{3,}\\b',
                        soup.get_text(
                            separator=' '
                        ).lower()
                    )

                    stops = {
                        'the', 'and', 'with',
                        'for', 'this', 'that',
                        'your', 'from',
                        'bosch', 'home',
                        'our', 'siemens'
                    }

                    filtered_words = [
                        w for w in words
                        if w not in stops
                    ]

                    if not filtered_words:

                        st.warning(
                            "No meaningful text found."
                        )

                    else:

                        total_words = len(
                            filtered_words
                        )

                        freq_list = Counter(
                            filtered_words
                        ).most_common(20)

                        df_freq = pd.DataFrame(
                            freq_list,
                            columns=["Keyword", "Count"]
                        )

                        df_freq["Density (%)"] = (
                            df_freq["Count"].apply(
                                lambda x: round(
                                    (x / total_words) * 100,
                                    2
                                )
                            )
                        )

                        st.bar_chart(
                            df_freq.set_index(
                                "Keyword"
                            )
                        )

                        st.dataframe(
                            df_freq,
                            use_container_width=True
                        )

                        if target_kw:

                            kw = target_kw.lower()

                            kw_count = (
                                filtered_words.count(kw)
                            )

                            kw_density = round(
                                (kw_count / total_words) * 100,
                                2
                            )

                            st.metric(
                                "Target Keyword Density",
                                f"{kw_density}%"
                            )

                # =====================================================
                # 🖼️ Image & Ghost Audit
                # =====================================================

                with tabs[5]:

                    st.subheader("Image Audit")

                    img_list = []

                    for img in soup.find_all('img'):

                        try:

                            src = urljoin(
                                url_input,
                                img.get('src', '')
                            )

                            size, _ = get_image_details(
                                src,
                                session
                            )

                            img_list.append({
                                "File": src.split('/')[-1],
                                "Size (KB)": round(size, 2),
                                "Status": (
                                    "🚩 LARGE"
                                    if size > 1000
                                    else "✅ OK"
                                )
                            })

                        except:
                            continue

                    df_images = pd.DataFrame(
                        img_list
                    )

                    if df_images.empty:

                        st.info(
                            "No images found."
                        )

                    else:

                        st.dataframe(
                            df_images
                        )

                    ghosts = []

                    if (
                        "/.webp" in html_content
                        or "/.jpg" in html_content
                    ):

                        ghosts.append({
                            "Type": "SYNTAX",
                            "Details": (
                                "Missing filename before extension"
                            )
                        })

                    df_ghosts = pd.DataFrame(
                        ghosts
                    )

                    if df_ghosts.empty:

                        st.success(
                            "No Ghost issues found."
                        )

                    else:

                        st.dataframe(
                            df_ghosts
                        )

        except Exception as e:

            st.error(f"Audit failed: {e}")


if __name__ == "__main__":
    render()
