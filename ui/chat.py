import httpx
import streamlit as st

import kosh_client as kosh

st.title("💬 Ask Kosh")

with st.sidebar:
    try:
        available = kosh.collections()
    except httpx.HTTPError:
        st.error("The Kosh API is not running. Start it with:\n\n`uv run uvicorn app.api.main:app --port 8010`")
        st.stop()
    choice = st.selectbox("Collection", ["All collections"] + [c["name"] for c in available])
    for c in available:
        st.caption(f"**{c['name']}**: {c['documents']} documents, {c['chunks']} chunks")
    if st.button("➕ New chat", use_container_width=True):
        st.session_state.chat_id = None
        st.session_state.messages = []
    st.subheader("Past chats")
    for chat in kosh.chats():
        current = chat["id"] == st.session_state.get("chat_id")
        if st.button(chat["title"], key=f"chat-{chat['id']}", type="primary" if current else "secondary",
                     use_container_width=True):
            st.session_state.chat_id = chat["id"]
            st.session_state.messages = kosh.chat_messages(chat["id"])
            st.rerun()  # redraw so the chosen chat is highlighted
    if st.session_state.get("chat_id") and st.button("🗑️ Delete this chat", use_container_width=True):
        kosh.delete_chat(st.session_state.chat_id)
        st.session_state.chat_id = None
        st.session_state.messages = []
        st.rerun()
collection = None if choice == "All collections" else choice

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.chat_id = None  # None = a new chat, saved when the first question is asked


def show_steps(steps: list[str]) -> None:
    """The agent's reasoning, folded away under the answer."""
    if steps:
        with st.expander(f"🧠 How Kosh found this ({len(steps)} steps)"):
            for step in steps:
                st.markdown(step)

def show_sources(citations: list[dict], sources: list[dict]) -> None:
    """Cited sources as links, plus everything retrieved (with rerank scores) in a fold-out."""
    for c in citations:
        st.markdown(f"[{c['number']}] [{c['section'] or 'source'} ↗]({kosh.to_url(c['link'])})")
    if sources:
        with st.expander(f"🔎 {len(sources)} chunks retrieved"):
            for i, s in enumerate(sources, start=1):
                loc = s["locator"]
                st.markdown(f"**[{i}]** score `{s['score']}` · {loc.get('section') or loc['uri']}")
                st.caption(s["text"][:400])

def show_unsupported(parts: list[str]) -> None:
    """What the self-check could not find in the sources."""
    if parts:
        st.warning("Not found in the sources, so check these yourself:\n\n" + "\n\n".join(parts))

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            show_steps(msg["steps"])
            show_sources(msg["citations"], msg["sources"])

if question := st.chat_input("Ask a question about your sources..."):
    first_question = st.session_state.chat_id is None
    if first_question:
        st.session_state.chat_id = kosh.new_chat(question)  # the first question becomes the chat's title
    kosh.save_message(st.session_state.chat_id, "user", question)
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        thinking = st.status("Kosh is searching and checking sources...", expanded=True)
        result = {"steps": [], "sources": [], "citations": [], "unsupported": []}

        def tokens():
            for event, data in kosh.stream_query(question, collection):
                if event == "step":
                    result["steps"].append(data)
                    thinking.write(data)
                elif event == "sources":
                    result["sources"] = data
                    thinking.update(
                        label=f"🧠 {len(result['steps'])} steps done, writing the answer (first words take ~40 s on CPU)",
                        state="complete",
                        expanded=False,
                    )
                elif event == "token":
                    yield data
                elif event == "done":
                    result["citations"] = data["citations"]
                    thinking.update(label="🔍 Checking the answer against the sources...", state="running")
                elif event == "check":
                    result["unsupported"] = data
                    thinking.update(label=f"🧠 {len(result['steps'])} steps done", state="complete")

        text = st.write_stream(tokens())
        show_unsupported(result["unsupported"])
        show_sources(result["citations"], result["sources"])

    st.session_state.messages.append({"role": "assistant", "content": text, **result})
    kosh.save_message(st.session_state.chat_id, "assistant", text, result)
    if first_question:
        st.rerun()  # show the new chat in the sidebar
