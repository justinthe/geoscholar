"""GeoScholar chat UI. Talks to the API over HTTP; loads no models itself.

    streamlit run ui/app.py
"""
import json
import os

import requests
import streamlit as st

API_URL = os.environ.get("GEOSCHOLAR_API_URL", "http://localhost:8000")


def iter_sse(lines):
    """Turn Server-Sent Event lines into (event, data) pairs."""
    event = None
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            yield event, json.loads(line[len("data:"):].strip())
            event = None


@st.cache_data(ttl=15, show_spinner=False)
def get_health():
    try:
        return requests.get(f"{API_URL}/health", timeout=5).json()
    except Exception:
        return None


def show_sources(sources, cited):
    with st.expander(f"Sources ({len(sources)} retrieved, {len(set(cited))} cited)"):
        for s in sources:
            mark = "cited" if s["n"] in cited else "not cited"
            st.markdown(f"**S{s['n']}** · [{s['title']}]({s['url']}) ({s['year']}) · "
                        f"*{s['section']}* · {mark}")
            st.caption(s["text"][:500] + ("..." if len(s["text"]) > 500 else ""))


def show_meta(result):
    t = result["timings_ms"]
    st.caption(f"retrieve {t['retrieve']:.0f} ms · rerank {t['rerank']:.0f} ms · "
               f"generate {t['generate'] / 1000:.1f} s · {result.get('tokens_per_s') or '?'} tokens/s")


# ---------- page ----------

st.set_page_config(page_title="GeoScholar", layout="centered")
st.title("GeoScholar")
st.caption("Ask questions about recent remote sensing papers on arXiv. Answers cite their sources.")

with st.sidebar:
    st.subheader("Status")
    health = get_health()
    if health is None:
        st.error(f"API not reachable at {API_URL}")
    else:
        st.write(f"Qdrant: {'ok' if health['qdrant'] else 'down'} · "
                 f"Ollama: {'ok' if health['ollama'] else 'not ready'}")
        st.write(f"{health['chunks'] or 0:,} chunks indexed · model `{health['llm']}`")
        if not health["chunks"]:
            st.warning("The index is empty. Run an ingestion first (see the README).")
    st.subheader("Filters")
    use_year = st.checkbox("Only recent papers")
    year_from = st.number_input("From year", min_value=1990, max_value=2100, value=2024,
                                disabled=not use_year)
    if st.button("Clear chat"):
        st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("result"):
            show_sources(m["result"]["sources"], m["result"]["cited"])
            show_meta(m["result"])

question = st.chat_input("e.g. Which datasets are used to evaluate SAR flood mapping?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        box = st.empty()
        box.markdown("_Searching papers..._")
        text, result = "", None
        payload = {"question": question, "year_from": int(year_from) if use_year else None}
        try:
            with requests.post(f"{API_URL}/query/stream", json=payload, stream=True,
                               timeout=(5, 300)) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f"API error {resp.status_code}: {resp.text[:300]}")
                for event, data in iter_sse(resp.iter_lines()):
                    if event == "token":
                        text += data["text"]
                        box.markdown(text + " ▌")        # cursor while writing
                    elif event == "done":
                        result = data
                    elif event == "error":
                        raise RuntimeError(data["detail"])
        except Exception as exc:
            box.empty()
            st.error(f"Something went wrong: {exc}")

        if result:
            box.markdown(result["answer_display"])
            show_sources(result["sources"], result["cited"])
            show_meta(result)
            st.session_state.messages.append(
                {"role": "assistant", "content": result["answer_display"], "result": result})