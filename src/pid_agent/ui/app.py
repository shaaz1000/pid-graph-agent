"""Streamlit chat interface over the existing agent.  Run with: uv run pid-agent-ui

Each question is one independent PidAgent.ask call. Earlier messages stay on screen for
convenience only; they are not sent to the model.
"""

from __future__ import annotations

import streamlit as st

from pid_agent.config import load_settings
from pid_agent.errors import PidAgentError
from pid_agent.ui import session
from pid_agent.ui.view_model import EXAMPLE_QUESTIONS, AnswerView, build_view, error_view

st.set_page_config(page_title="P&ID Engineering Assistant", layout="wide")
st.markdown(
    """
    <style>
      .block-container {max-width: 980px; padding-top: 2.2rem;}
      [data-testid="stSidebar"] .block-container {padding-top: 1.6rem;}
      .pid-meta {font-size: 0.82rem; color: rgba(128,128,128,0.95); letter-spacing: 0.02em;}
      .pid-label {font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(128,128,128,0.95); margin-bottom: 0.1rem;}
      .pid-value {font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.86rem; margin-bottom: 0.7rem;}
      .pid-ok {color: #1f8a4c; font-weight: 600;}
      .pid-warn {color: #b26a00; font-weight: 600;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Loading the P&ID through pyDEXPI…")
def _graph(data_file: str):
    return session.load_graph(load_settings())


@st.cache_resource(show_spinner=False)
def _agent(provider: str, model: str, data_file: str):
    return session.build_agent(load_settings(), _graph(data_file).tools)


def _field(label: str, value: str) -> None:
    st.markdown(f'<div class="pid-label">{label}</div><div class="pid-value">{value}</div>', unsafe_allow_html=True)


def _sidebar(settings, facts: dict) -> None:
    with st.sidebar:
        st.markdown("### P&ID Graph Agent")
        _field("Loaded drawing", facts["file"])
        _field("Provider", settings.llm_provider)
        _field("Model", settings.llm_model or "(LLM_MODEL not set)")
        _field("Plant graph", f"{facts['plant'][0]} nodes · {facts['plant'][1]} edges")
        _field("Conceptual graph", f"{facts['conceptual'][0]} nodes · {facts['conceptual'][1]} edges")
        if st.button("New conversation", use_container_width=True):
            st.session_state.history = []
            st.rerun()
        with st.expander("Example questions"):
            for category, question in EXAMPLE_QUESTIONS:
                if st.button(question, key=f"side-{category}", use_container_width=True):
                    st.session_state.pending = question
                    st.rerun()
        with st.expander("About the graph"):
            st.markdown(
                "pyDEXPI parses the DEXPI file into the **plant graph** (every object; used for "
                "properties and provenance) and abstracts it into the **conceptual graph** "
                "(equipment, valves, fittings and instrument functions joined by pipes; used for "
                "connectivity and flow direction)."
            )
            st.markdown("**Entities by category**")
            for name, count in sorted(facts["entities"].items()):
                st.markdown(f"- {name.replace('_', ' ')}: {count}")
            st.markdown("**Connections by type**")
            for name, count in sorted(facts["connections"].items()):
                st.markdown(f"- {name.replace('_', ' ')}: {count}")
        st.caption("Each question is an independent agent run. Earlier messages are displayed but not sent to the model.")


def _empty_state() -> None:
    st.markdown("##### Try one of these")
    columns = st.columns(3)
    for i, (category, question) in enumerate(EXAMPLE_QUESTIONS):
        with columns[i % 3].container(border=True):
            st.markdown(f'<div class="pid-label">{category}</div>', unsafe_allow_html=True)
            if st.button(question, key=f"card-{category}", use_container_width=True):
                st.session_state.pending = question
                st.rerun()


def _render(view: AnswerView) -> None:
    if view.state == "provider_failure":
        st.warning("The model provider could not be reached, so this question was not answered. This is not a statement about the P&ID.")
    elif view.state == "withheld":
        st.info("The model's draft was not supported by the graph evidence. What follows is assembled directly from tool results.")
    elif view.state == "config_error":
        st.warning(view.notices[0].detail)
        return
    st.markdown(view.answer)

    if view.candidates:
        with st.container(border=True):
            st.markdown("**Several entities match.** Ask again with one of these identifiers:")
            for c in view.candidates:
                left, right = st.columns([2, 3])
                left.code(c.id, language=None)
                right.markdown(f"{c.name} · {c.type}" + (f"  \n<span class='pid-meta'>{c.reason}</span>" if c.reason else ""), unsafe_allow_html=True)

    g = view.grounding
    if g is not None:
        css, mark = ("pid-ok", "✓") if g.ok else ("pid-warn", "!")
        st.markdown(f'<span class="{css}">{mark} {g.label}</span> <span class="pid-meta">· {view.usage}</span>', unsafe_allow_html=True)

    if view.summary:
        with st.expander("How this answer was found"):
            for line in view.summary:
                st.markdown(f"`{line}`")
            st.caption("These are the graph operations that were executed, in order. The model chose them; the results came from the graph.")
    if view.steps:
        with st.expander(f"Tool calls ({len(view.steps)})"):
            for step in view.steps:
                with st.container(border=True):
                    suffix = "" if step.executed else " · not executed"
                    st.markdown(f"**Step {step.number} · `{step.tool}`** <span class='pid-meta'>· {step.status}{suffix}</span>", unsafe_allow_html=True)
                    if step.inputs:
                        st.markdown('<div class="pid-label">Input</div>', unsafe_allow_html=True)
                        st.code("\n".join(step.inputs), language=None)
                    if step.lines:
                        st.markdown('<div class="pid-label">Result</div>', unsafe_allow_html=True)
                        st.code("\n".join(step.lines), language=None)
                    with st.popover("View raw result"):
                        st.json(step.raw)
    if view.evidence:
        with st.expander(f"Graph evidence ({len(view.evidence)})"):
            for e in view.evidence:
                st.markdown(f"**{e.kind}** · `{e.id}`  \n<span class='pid-meta'>{e.source_graph} · {', '.join(e.source_object_ids)}</span>", unsafe_allow_html=True)
                if e.fact:
                    st.caption(e.fact)
    if g is not None:
        with st.expander("Grounding"):
            st.markdown(f"**{g.label}.** {g.detail}")
            for claims in g.rejected:
                st.markdown(f"- A draft was rejected for unsupported claims: `{claims}`")
            for claim in g.unsupported:
                st.markdown(f"- Unsupported: {claim}")
            st.caption("A deterministic check compares identifiers, numbers, units and DN values in the answer with the tool results. It is not a confidence score.")
    if view.notices or view.warnings:
        with st.expander(f"Warnings and graph notes ({len(view.notices) + len(view.warnings)})"):
            for notice in view.notices:
                st.markdown(f"**{notice.title}.** {notice.detail}")
            for warning in view.warnings:
                st.markdown(f"- {warning}")


def _ask(settings, question: str) -> AnswerView:
    try:
        agent = _agent(settings.llm_provider, settings.llm_model, str(settings.data_file))
        return build_view(agent.ask(question))
    except PidAgentError as exc:
        return error_view(question, str(exc))


def main() -> None:
    settings = load_settings()
    try:
        graph = _graph(str(settings.data_file))
    except PidAgentError as exc:
        st.error(f"The P&ID could not be loaded: {exc}")
        return
    st.session_state.setdefault("history", [])
    _sidebar(settings, graph.facts)

    st.markdown("## P&ID Engineering Assistant")
    st.markdown(
        '<div class="pid-meta">Ask questions about equipment, piping, connectivity, instrumentation and properties in the loaded P&ID.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if not st.session_state.history and "pending" not in st.session_state:
        _empty_state()
    for view in st.session_state.history:
        with st.chat_message("user"):
            st.markdown(view.question)
        with st.chat_message("assistant"):
            _render(view)

    typed = st.chat_input("Ask about the P&ID")
    question = st.session_state.pop("pending", None) or typed
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Querying the graph…"):
                view = _ask(settings, question)
            _render(view)
        st.session_state.history.append(view)


main()
