import streamlit as st
from auth.utils import verify_user

def render():
    st.markdown("<h1 style='text-align: center; font-family:Syne;'>🔐 Serpify Login</h1>", unsafe_allow_html=True)
    
    # Center the login form
    _, col, _ = st.columns([1, 2, 1])
    
    with col:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)

            if submit:
                user_id = verify_user(username, password)
                if user_id:
                    st.session_state["user_id"] = user_id
                    st.session_state["username"] = username
                    st.success("Login successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")