import streamlit as st

st.set_page_config(page_title="Kosh", page_icon="📚", layout="wide")

page = st.navigation([
    st.Page("chat.py", title="Chat", icon="💬"),
    st.Page("sources.py", title="Sources", icon="📁"),
    st.Page("quality.py", title="Quality", icon="📊"),
])
page.run()
