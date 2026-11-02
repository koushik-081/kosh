import httpx
import streamlit as st

import kosh_client as kosh

st.title("📁 Sources")

with st.form("add_source", clear_on_submit=True):
    st.subheader("Add a source")
    collection = st.text_input("Collection", help="An existing name adds to it; a new name creates a collection")
    url = st.text_input("Web page, GitHub repo or YouTube URL")
    subpath = st.text_input("GitHub only: just this folder (optional)", placeholder="e.g. docs/en/docs/tutorial")
    pdf = st.file_uploader("…or a PDF", type="pdf")
    if st.form_submit_button("Add"):
        if not collection or not (url or pdf):
            st.error("Give a collection name and a URL or a PDF.")
        else:
            with st.spinner("Reading and embedding... a big GitHub repo can take several minutes on CPU"):
                try:
                    if pdf:
                        added = kosh.ingest_pdf(collection, pdf.name, pdf.getvalue())
                    else:
                        added = kosh.ingest(url, collection, subpath)
                    st.success(f"{added['found']} chunks found, {added['added']} new ones saved to **{collection}**")
                except httpx.HTTPStatusError as e:
                    st.error(e.response.json().get("detail", str(e)))

st.subheader("What Kosh knows")
for c in kosh.collections():
    with st.expander(f"**{c['name']}**: {c['documents']} documents, {c['chunks']} chunks"):
        docs = kosh.documents(c["name"])
        st.dataframe(
            [{"Type": d["source_type"], "Document": d["document_id"].split(":", 1)[1], "Chunks": d["chunks"]}
             for d in docs],
            hide_index=True,
            width="stretch",
        )
        remove = st.selectbox("Remove a document", [""] + [d["document_id"] for d in docs], key=f"rm-{c['name']}")
        if remove and st.button("🗑️ Remove", key=f"rm-btn-{c['name']}"):
            kosh.delete_document(c["name"], remove)
            st.rerun()