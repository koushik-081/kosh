import streamlit as st

st.set_page_config(page_title="Kosh", page_icon="📚", layout="wide")

page = st.navigation([st.Page("chat.py", title="Chat", icon="💬")])
page.run()
