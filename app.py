"""Investor Ops & Intelligence Suite — main Streamlit entry point.

Run: streamlit run app.py
"""
import json
from pathlib import Path

import streamlit as st

from config import load_env, MCP_MODE
from session_init import init_session_state
from pillar_a.faq_engine import query as faq_query
from pillar_a.ingest import get_collection
from pillar_b.pipeline_orchestrator import run_pipeline
from pillar_b.voice_agent import VoiceAgent
from pillar_c.mcp_client import MCPClient
from pillar_c.hitl_panel import render as render_hitl

# ── 1. Bootstrap ──────────────────────────────────────────────────────────────
load_env()
st.set_page_config(
    page_title="INDMoney Advisor Suite",
    page_icon="📊",
    layout="wide",
)
init_session_state(st.session_state)

# Reload MCP queue from disk if session is fresh (handles page reloads)
if not st.session_state["mcp_queue"]:
    state_file = Path("data/mcp_state.json")
    if state_file.exists():
        try:
            st.session_state["mcp_queue"] = json.loads(state_file.read_text())
        except json.JSONDecodeError:
            pass

# ── 2. Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 INDMoney Advisor Suite")
    st.caption("Investor Ops & Intelligence Suite — Demo")
    st.markdown("---")

    # Corpus status
    try:
        faq_count = get_collection("mf_faq_corpus").count()
        fee_count = get_collection("fee_corpus").count()
        st.success(f"✅ FAQ corpus: {faq_count} chunks")
        st.success(f"✅ Fee corpus: {fee_count} chunks")
    except Exception:
        st.error("❌ Corpus not loaded — run:")
        st.code("python scripts/ingest_corpus.py")

    st.markdown("---")

    # Pulse status
    if st.session_state["pulse_generated"]:
        st.info(f"📊 Top theme: **{st.session_state['top_theme']}**")
    else:
        st.warning("📊 No pulse generated yet")

    # MCP pending count
    pending = sum(1 for a in st.session_state["mcp_queue"] if a["status"] == "pending")
    st.metric("Pending Approvals", pending)

    st.markdown("---")
    if st.button("🔄 Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        Path("data/mcp_state.json").unlink(missing_ok=True)
        st.rerun()

# ── 3. Tabs ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📚 Smart-Sync FAQ",
    "📊 Review Pulse & Voice",
    "✅ Approval Center",
])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Smart-Sync FAQ
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Smart-Sync Mutual Fund FAQ")
    st.caption(
        "Ask factual questions about SBI Mutual Fund schemes and fees. "
        "Facts only — no investment advice."
    )

    if not st.session_state["chat_history"]:
        st.info(
            "**Try these compound questions:**\n"
            "- What is the exit load for SBI ELSS and how is the expense ratio calculated?\n"
            "- Can I redeem SBI Bluechip within 6 months and what fees apply?\n"
            "- What is the minimum SIP for SBI Small Cap and what are the fee components?"
        )

    # Display conversation history
    for entry in st.session_state["chat_history"]:
        with st.chat_message("user"):
            st.write(entry["content"])
        with st.chat_message("assistant"):
            response = entry["response"]
            if response.refused:
                st.warning(f"⚠ {response.refusal_msg}")
            elif response.bullets:
                for b in response.bullets:
                    st.markdown(f"- {b}")
            else:
                st.write(response.prose)
            for src in response.sources:
                st.caption(f"Source: {src}")
            st.caption(f"Last updated from sources: {response.last_updated}")

    user_question = st.chat_input("Ask a factual question about SBI Mutual Funds...")
    if user_question:
        with st.spinner("Retrieving answer..."):
            faq_query(user_question, st.session_state)
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Review Pulse & Voice Agent
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Review Pulse & Voice Agent")

    # ── Review Pipeline section ──────────────────────────────────────────────
    st.markdown("#### Weekly Review Pulse")
    uploaded_file = st.file_uploader("Upload reviews CSV", type="csv")

    if uploaded_file and st.button("▶ Run Pipeline"):
        with st.spinner("Processing reviews..."):
            try:
                result = run_pipeline(uploaded_file, st.session_state)
                st.success("Pipeline complete!")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.subheader("Top Themes")
                    for theme in result["top_3"]:
                        st.markdown(f"- {theme}")
                with col2:
                    st.subheader("User Quotes")
                    for q in result["quotes"]:
                        st.markdown(f"*\"{q['quote']}\"*  — Rating: {q['rating']}/5")
                with col3:
                    st.subheader("Weekly Pulse")
                    st.write(result["pulse"])
                    st.caption(f"Word count: {result['word_count']}")

                if result.get("action_ideas"):
                    st.markdown("#### Action Ideas")
                    for idea in result["action_ideas"]:
                        st.markdown(f"- {idea}")

                st.markdown("#### Fee Context")
                for bullet in result["fee_bullets"]:
                    st.markdown(f"- {bullet}")
                for src in result["fee_sources"]:
                    st.caption(f"Source: {src}")
                st.caption(f"Last checked: {result['fee_checked']}")
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")

    # ── Voice Agent section ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Voice Appointment Booking")

    pulse_ready = st.session_state.get("pulse_generated", False)
    top_theme   = st.session_state.get("top_theme", "")

    if pulse_ready:
        st.success(f"✓ Pulse generated. Top theme this week: **{top_theme}**")
        start_call = st.button("▶ Start Call", key="start_call_btn")
    else:
        st.warning("⚠ Generate a Weekly Pulse first. Upload a reviews CSV above.")
        start_call = False

    if start_call:
        if "voice_agent" not in st.session_state:
            st.session_state["voice_agent"] = VoiceAgent(
                session=st.session_state,
                calendar_path="data/mock_calendar.json",
            )
            st.session_state["voice_turn"] = 0
            greeting_text, greeting_audio = st.session_state["voice_agent"].get_greeting()
            st.session_state["greeting_text"]  = greeting_text
            st.session_state["greeting_audio"] = greeting_audio

    if "voice_agent" in st.session_state:
        st.markdown(f"**Agent:** {st.session_state.get('greeting_text', '')}")
        if st.session_state.get("greeting_audio"):
            st.audio(st.session_state["greeting_audio"], format="audio/mp3")

        agent = st.session_state["voice_agent"]
        turn  = st.session_state.get("voice_turn", 0)

        user_input = st.text_input(
            "Your response:",
            key=f"voice_input_{turn}",
        )

        if user_input:
            response_text, response_audio = agent.step(user_input)
            st.markdown(f"**Agent:** {response_text}")
            if response_audio:
                st.audio(response_audio, format="audio/mp3")
            st.session_state["voice_turn"] = turn + 1

            if agent.state in ("BOOKED", "WAITLIST"):
                code = st.session_state.get("booking_code", "N/A")
                st.success(f"✓ Appointment booked! Code: **{code}**")
                st.info("Check the Approval Center tab to review and approve calendar, notes, and email.")

# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — HITL Approval Center
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### HITL Approval Center")
    st.caption("Review and approve all AI-generated actions before they execute.")

    pending_count = sum(
        1 for a in st.session_state["mcp_queue"] if a["status"] == "pending"
    )
    if pending_count > 0:
        st.warning(f"⚠ {pending_count} action(s) awaiting your approval")

    mcp_client = MCPClient(mode=MCP_MODE)
    render_hitl(session=st.session_state, mcp_client=mcp_client)
