import streamlit as st
import streamlit.components.v1 as components

INFO = {
    "title": "Bulk URL Opener",
    "icon": "🚀",
    "description": "Instantly launch multiple URLs in separate browser tabs for rapid manual verification."
}

def render():
    st.markdown("""
    <div class="tool-header">
        <div class="tool-icon">🚀</div>
        <div>
            <div class="tool-title">Bulk URL Opener</div>
            <div class="tool-sub">Paste URLs and open them all in separate tabs instantly</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. INPUT AREA
    raw_input = st.text_area(
        "Paste URLs (one per line)", 
        placeholder="google.com\nbosch.com\nhttps://github.com",
        height=300
    )

    if raw_input:
        # Clean the links
        links = [line.strip() for line in raw_input.split('\n') if line.strip()]
        
        # Add protocol if missing
        processed_links = []
        for url in links:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            processed_links.append(url)

        st.info(f"📋 Found **{len(processed_links)}** URLs ready to launch.")

        # 2. THE JAVASCRIPT OPENER
        # Browsers block "popups" if they aren't triggered by a real click.
        # This code creates a specialized button that the browser trusts.
        
        links_js = str(processed_links) # Convert Python list to JS array string
        
        open_button_js = f"""
        <script>
        function openAll() {{
            const urls = {links_js};
            urls.forEach(url => {{
                window.open(url, '_blank');
            }});
        }}
        </script>
        <button onclick="openAll()" style="
            background-color: #4ade80;
            color: #0a0f0a;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-family: 'Syne', sans-serif;
            font-weight: 700;
            cursor: pointer;
            width: 100%;
            font-size: 16px;
        ">
            🚀 Launch All {len(processed_links)} Tabs
        </button>
        """
        
        components.html(open_button_js, height=70)
        
        st.warning("⚠️ **Note:** Your browser might block these as 'popups'. Look for a small icon in your URL bar and select **'Always allow'** to make this work.")

if __name__ == "__main__":
    render()