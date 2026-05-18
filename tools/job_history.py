import streamlit as st
import pandas as pd
import json
import os
import time
from jobs.job_manager import start_job
from analytics.db import get_conn
from core.tool_registry import get_builder

def render():
    st.markdown("""
    <div class="tool-header">
        <div class="tool-icon">📜</div>
        <div>
            <div class="tool-title">Job History</div>
            <div class="tool-sub">Review and download your past SEO audits</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. Identity Check
    user_id = st.session_state.get("user_id", "admin")
    conn = get_conn()
    
    # 2. Fetch Job History (Limit to 50 for performance)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 50", 
            conn, params=(user_id,)
        )
    except Exception as e:
        st.error(f"Database error: {e}")
        return
    finally:
        conn.close()

    if df.empty:
        st.info("No audit history found yet. Start your first crawl to see results here!")
        return

    # 3. Render Job List
    for _, row in df.iterrows():
        # Format the timestamp for human readability
        created_dt = time.strftime('%Y-%m-%d %H:%M', time.localtime(row['created_at']))
        job_id = row['job_id']
        tool_name = row['tool'] # Standardized lowercase ID (e.g., 'keyword')
        
        with st.expander(f"📦 {tool_name.upper()} | {created_dt}"):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.write(f"**Job ID:** `{job_id}`")
                st.caption(f"Parameters: {row['params']}")
            
            with col2:
                # Visual status indicator
                status_map = {
                    "completed": "🟢 COMPLETED",
                    "failed": "🔴 FAILED",
                    "running": "🟡 RUNNING",
                    "queued": "⚪ QUEUED"
                }
                current_status = row['status'].lower()
                st.write(f"**Status:** {status_map.get(current_status, current_status.upper())}")

            with col3:
                # 📥 Download Result Logic
                if current_status == "completed" and row["result_json"]:
                    if os.path.exists(row["result_json"]):
                        with open(row["result_json"], "rb") as f:
                            st.download_button(
                                "Download JSON",
                                data=f,
                                file_name=f"Result_{tool_name}_{job_id}.json",
                                key=f"dl_{job_id}"
                            )
                
                # 🔄 SAFE RETRY LOGIC (Thread-safe & Non-blocking)
                if st.button("Retry Job", key=f"btn_retry_{job_id}"):
                    
                    # A. Prevent duplicate button spamming
                    if st.session_state.get(f"retrying_{job_id}"):
                        st.warning("Retry already in progress...")
                        return
                    
                    st.session_state[f"retrying_{job_id}"] = True

                    # B. Defensive JSON Parsing (Prevents crash on corrupted DB entries)
                    try:
                        params = json.loads(row["params"])
                    except (json.JSONDecodeError, TypeError):
                        st.error("Invalid job parameters. Cannot re-run this audit.")
                        st.session_state.pop(f"retrying_{job_id}", None)
                        return

                    # C. Registry Validation (Checks if the tool is mapped for retry)
                    builder = get_builder(tool_name, params)
                    
                    if not callable(builder):
                        st.warning(f"Retry logic not configured for tool: '{tool_name}'")
                        st.session_state.pop(f"retrying_{job_id}", None)
                        return
                    
                    # D. Launch New Job
                    try:
                        new_id = start_job(user_id, tool_name, params, builder)
                        st.success(f"✅ {tool_name.capitalize()} job queued: `{new_id}`")
                        
                        # E. Cleanup and Refresh UI
                        st.session_state.pop(f"retrying_{job_id}", None)
                        time.sleep(1) # Small pause for user to read success msg
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to queue retry: {e}")
                        st.session_state.pop(f"retrying_{job_id}", None)
if __name__ == "__main__":
    render()