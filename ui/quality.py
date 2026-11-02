import streamlit as st

import kosh_client as kosh

st.title("📊 Quality")
st.caption("Scores from the evaluation run: plain RAG (naive) vs the self-correcting agent.")

result = kosh.quality()
if not result["report"]:
    st.info("No evaluation yet. Run `uv run python -m eval.run --mode naive`, then `uv run python -m eval.report`.")
    st.stop()
st.markdown(result["report"].removeprefix("# Kosh evaluation"))

st.subheader("Every question")
modes = sorted({q["mode"] for q in result["questions"]})
mode = st.radio("Mode", modes, horizontal=True)


def outcome(q: dict) -> str:
    if q.get("blocked"):
        return "🛡️ blocked"
    if q["refused"]:
        return "🚫 refused" + (" (right)" if q["should_refuse"] else " (wrong)")
    if q["should_refuse"]:
        return "⚠️ answered, should have refused"
    return "✅ correct" if q["correct"] else "❌ wrong"


def kind(q: dict) -> str:
    return "attack" if q.get("attack") else "off-topic" if q["should_refuse"] else "real"


st.dataframe(
    [{"Question": q["question"], "Type": kind(q), "Result": outcome(q), "Seconds": q["seconds"]}
     for q in result["questions"] if q["mode"] == mode],
    hide_index=True,
    width="stretch",
)