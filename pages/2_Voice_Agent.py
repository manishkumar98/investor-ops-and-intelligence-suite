"""
Page 2 — Full Voice Agent (Dalal Street Advisors Advisor Scheduling)
Adapted from voice-agent/phase5/ui/app.py and wired to phase6_pillar_b_voice.
"""
from __future__ import annotations

import sys
import os
import hashlib
from pathlib import Path

# ── sys.path: make phase6 sub-packages importable as  src.booking / src.dialogue / etc.
_page_dir = Path(__file__).resolve().parent          # pages/
_root_dir  = _page_dir.parent                        # investor_ops-and-intelligence_suit/
_p6_dir    = _root_dir / "phase6_pillar_b_voice"

# Expose phase6 sub-dirs as  src.*  (expected by the voice-agent import paths)
# We add  phase6_pillar_b_voice  as if it were the repo root that contains a "src" package
if str(_p6_dir) not in sys.path:
    sys.path.insert(0, str(_p6_dir))
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv(str(_root_dir / ".env"))
except ImportError:
    pass

# Point data paths at the project's data files (absolute so MCP tools find them)
os.environ["MOCK_CALENDAR_PATH"] = str(_root_dir / "data" / "mock_calendar.json")
os.environ.setdefault("TTS_PACE", "1.0")
os.environ.setdefault("SECURE_URL_DOMAIN", os.getenv("SECURE_BASE_URL", "http://localhost:8501"))
# Service account — must be absolute path for google-auth to load it
_sa_path = str(_root_dir / "config" / "service_account.json")
if os.path.exists(_sa_path):
    os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"] = _sa_path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Advisor Scheduling — Voice Agent",
    page_icon="🎙",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS (Dezerv-inspired: charcoal + warm gold) ──────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

#MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="collapsedControl"] { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }

:root {
    --bg-base:    #0A0C14;
    --bg-card:    #10131F;
    --bg-glass:   rgba(255,255,255,0.04);
    --border:     rgba(255,255,255,0.08);
    --gold-1:     #C9A84C;
    --gold-2:     #E8C96D;
    --gold-glow:  rgba(201,168,76,0.18);
    --gold-dim:   rgba(201,168,76,0.55);
    --text-1:     #F5F0E8;
    --text-2:     #9A9080;
    --text-3:     #6B6358;
    --green:      #22C55E;
    --red:        #EF4444;
}

html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
section.main > div {
    background: var(--bg-base) !important;
    color: var(--text-1) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.block-container { padding: 0 !important; max-width: 100% !important; margin: 0 !important; }

/* Ambient glow */
.stApp::before {
    content: '';
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
        radial-gradient(ellipse 80% 40% at 50% -5%, rgba(201,168,76,0.07) 0%, transparent 70%),
        radial-gradient(ellipse 40% 30% at 85% 100%, rgba(201,168,76,0.04) 0%, transparent 60%);
}

/* Header */
.dsa-header {
    position: sticky; top: 0; z-index: 100;
    background: rgba(10,12,20,0.95); backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 48px; height: 64px; width: 100%; box-sizing: border-box;
}
.dsa-logo-wrap { display: flex; align-items: center; gap: 12px; }
.dsa-logo-icon {
    width: 38px; height: 38px; border-radius: 10px;
    background: linear-gradient(135deg, var(--gold-1), #8a6820);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; flex-shrink: 0;
}
.dsa-logo-text { font-size: 1.05rem; font-weight: 800; color: var(--text-1); letter-spacing: -0.02em; }
.dsa-logo-sub  { font-size: 0.65rem; color: var(--gold-dim); letter-spacing: 0.08em; text-transform: uppercase; font-weight: 500; }
.dsa-nav { display: flex; gap: 32px; align-items: center; }
.dsa-nav a { font-size: 0.85rem; font-weight: 500; color: var(--text-2); text-decoration: none; transition: color 0.2s; }
.dsa-nav a:hover { color: var(--gold-2); }
@media (max-width: 768px) { .dsa-nav { display: none; } .dsa-header { padding: 0 20px; } }

/* Landing */
.lp-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(201,168,76,0.10); border: 1px solid rgba(201,168,76,0.28);
    border-radius: 100px; padding: 5px 16px;
    font-size: 0.75rem; font-weight: 600; color: var(--gold-2);
    letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 28px;
}
.lp-badge-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--gold-1); animation: gold-blink 2s infinite; }
@keyframes gold-blink { 0%,100%{opacity:1;} 50%{opacity:0.3;} }
.lp-title { font-size: 2.4rem; font-weight: 800; line-height: 1.15; color: var(--text-1); letter-spacing: -0.03em; margin-bottom: 14px; }
.lp-title span { background: linear-gradient(135deg, var(--gold-1), var(--gold-2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.lp-sub { font-size: 1rem; color: var(--text-2); line-height: 1.65; max-width: 400px; margin-bottom: 36px; }
.lp-wrap { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 56px 0 16px; }

/* Stat strip */
.stat-strip { display: flex; gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 16px; overflow: hidden; width: 100%; max-width: 440px; margin-bottom: 40px; }
.stat-cell { flex: 1; background: var(--bg-card); padding: 14px 10px; text-align: center; }
.stat-val { font-size: 1.15rem; font-weight: 700; color: var(--gold-2); margin-bottom: 2px; }
.stat-lbl { font-size: 0.72rem; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.05em; }

/* Disclaimer */
.disclaimer-box {
    background: rgba(201,168,76,0.05); border: 1px solid rgba(201,168,76,0.18);
    border-radius: 12px; padding: 14px 20px; font-size: 0.8rem; color: var(--text-2);
    max-width: 440px; text-align: left; margin-bottom: 32px; line-height: 1.65;
}
.disclaimer-box strong { color: var(--gold-2); }

/* Call UI */
.call-wrap { display: flex; flex-direction: column; align-items: center; padding: 48px 0 16px; text-align: center; }
.call-page-wrap { max-width: 680px; margin: 0 auto; padding: 0 20px; }
.ring-outer { width: 168px; height: 168px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-bottom: 28px; position: relative; }
.ring-outer.idle { background: var(--bg-card); box-shadow: 0 0 0 1px var(--border); }
.ring-outer.speaking { background: linear-gradient(145deg, #1a1408, #120e04); box-shadow: 0 0 0 2px var(--gold-1), 0 0 0 14px var(--gold-glow), 0 0 0 30px rgba(201,168,76,0.06), 0 0 60px 0px rgba(201,168,76,0.12); animation: gold-pulse 1.6s ease-in-out infinite; }
.ring-outer.listening { background: linear-gradient(145deg, #071a10, #051408); box-shadow: 0 0 0 2px #22c55e, 0 0 0 14px rgba(34,197,94,0.14), 0 0 0 30px rgba(34,197,94,0.05); animation: green-pulse 2s ease-in-out infinite; }
@keyframes gold-pulse { 0%,100%{box-shadow:0 0 0 2px var(--gold-1),0 0 0 14px var(--gold-glow),0 0 0 30px rgba(201,168,76,0.06),0 0 60px 0 rgba(201,168,76,0.12);} 50%{box-shadow:0 0 0 2px var(--gold-2),0 0 0 22px rgba(201,168,76,0.26),0 0 0 44px rgba(201,168,76,0.09),0 0 80px 0 rgba(201,168,76,0.18);} }
@keyframes green-pulse { 0%,100%{box-shadow:0 0 0 2px #22c55e,0 0 0 14px rgba(34,197,94,0.14),0 0 0 30px rgba(34,197,94,0.05);} 50%{box-shadow:0 0 0 2px #4ade80,0 0 0 22px rgba(34,197,94,0.22),0 0 0 44px rgba(34,197,94,0.08);} }
.caller-avatar { width: 128px; height: 128px; border-radius: 50%; background: linear-gradient(145deg, #1e1608, #120e04); border: 1.5px solid rgba(201,168,76,0.30); display: flex; align-items: center; justify-content: center; font-size: 58px; }
.caller-name { font-size: 1.35rem; font-weight: 700; color: var(--text-1); margin-bottom: 4px; letter-spacing: -0.02em; }
.caller-firm { font-size: 0.82rem; color: var(--gold-dim); letter-spacing: 0.08em; text-transform: uppercase; font-weight: 500; margin-bottom: 28px; }
.status-pill { display: inline-flex; align-items: center; gap: 8px; background: var(--bg-glass); border: 1px solid var(--border); border-radius: 100px; padding: 7px 20px; font-size: 0.82rem; color: var(--text-2); margin-bottom: 32px; }
.s-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.s-dot.gold  { background: var(--gold-1); animation: gold-blink 0.9s infinite; }
.s-dot.green { background: var(--green);  animation: gold-blink 1.4s infinite; }
.s-dot.dim   { background: var(--text-3); }
.agent-caption { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; padding: 16px 22px; font-size: 0.9rem; color: var(--text-2); text-align: center; max-width: 500px; line-height: 1.7; margin-bottom: 28px; min-height: 50px; font-style: italic; }
.backend-status { font-size: 0.78rem; color: var(--gold-1); text-align: center; letter-spacing: 0.04em; min-height: 18px; margin-top: -18px; margin-bottom: 18px; font-style: italic; opacity: 0.85; }
.vad-live-status { font-size: 0.85rem; font-weight: 600; letter-spacing: 0.04em; text-align: center; min-height: 24px; margin-bottom: 10px; padding: 5px 18px; border-radius: 100px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); color: var(--text-2); display: inline-block; transition: color 0.3s, background 0.3s, border-color 0.3s; }
.vad-live-wrap { text-align: center; margin-bottom: 10px; min-height: 36px; }
.booking-success { background: linear-gradient(145deg,#0D1008,#0A0C06); border: 1px solid rgba(201,168,76,0.30); border-radius: 20px; padding: 32px 28px; text-align: center; max-width: 520px; margin: 0 auto 24px; }
.booking-success-icon { font-size: 2.8rem; margin-bottom: 10px; }
.booking-success-title { font-size: 1.2rem; font-weight: 700; color: var(--gold-2); margin-bottom: 4px; }
.booking-code-badge { display: inline-block; background: rgba(201,168,76,0.10); border: 1px solid rgba(201,168,76,0.35); border-radius: 8px; padding: 7px 22px; font-size: 1.4rem; font-weight: 800; color: var(--gold-2); letter-spacing: 4px; margin: 12px 0 14px; }
/* Contact details link strip */
.booking-link { margin-top: 18px; background: rgba(201,168,76,0.06); border: 1px solid rgba(201,168,76,0.22); border-radius: 12px; padding: 14px 18px; font-size: 0.85rem; color: var(--text-2); line-height: 1.6; }
.booking-link a { color: var(--gold-2); font-weight: 600; word-break: break-all; }
.booking-link a:hover { color: var(--gold-1); }
/* MCP status row */
.mcp-status-row { display: flex; gap: 12px; justify-content: center; margin: 18px 0 0; flex-wrap: wrap; }
.mcp-pill { display: inline-flex; align-items: center; gap: 6px; padding: 6px 16px; border-radius: 100px; font-size: 0.82rem; font-weight: 600; border: 1px solid; }
.mcp-ok  { background: rgba(34,197,94,0.10);  border-color: rgba(34,197,94,0.35);  color: #4ade80; }
.mcp-err { background: rgba(239,68,68,0.10);  border-color: rgba(239,68,68,0.35);  color: #f87171; }
.stButton > button[kind="primary"] { background: linear-gradient(135deg,var(--gold-1),#A8873A) !important; color: #0A0C14 !important; border: none !important; border-radius: 100px !important; font-weight: 700 !important; font-size: 0.95rem !important; padding: 13px 44px !important; box-shadow: 0 4px 24px rgba(201,168,76,0.35) !important; }
.stButton > button[kind="primary"]:hover { background: linear-gradient(135deg,var(--gold-2),var(--gold-1)) !important; box-shadow: 0 6px 32px rgba(201,168,76,0.50) !important; transform: translateY(-1px) !important; }
.stButton > button[kind="secondary"] { background: transparent !important; color: var(--text-3) !important; border: 1px solid var(--border) !important; border-radius: 100px !important; font-weight: 500 !important; font-size: 0.85rem !important; padding: 9px 28px !important; }
[data-testid="stAudioInput"] { position: fixed !important; top: -9999px !important; left: -9999px !important; width: 1px !important; height: 1px !important; overflow: hidden !important; pointer-events: none !important; }
hr { border-color: var(--border) !important; margin: 24px 0 !important; }
[data-testid="stMarkdownContainer"] p { color: var(--text-2) !important; }
.stSpinner > div { color: var(--gold-dim) !important; }
[data-testid="stRadio"] > div { flex-direction: row !important; }
[data-testid="stRadio"] label { color: var(--text-3) !important; font-size: 0.82rem !important; }
[data-testid="stRadio"] label[data-checked="true"] { color: var(--gold-2) !important; }
</style>
""", unsafe_allow_html=True)


# ── STT helper ──────────────────────────────────────────────────────────────
def _stt(audio_bytes: bytes, language: str = "en-IN") -> str:
    """STT: Groq Whisper → Google Cloud → Deepgram → offline (via STTEngine chain)."""
    os.environ["STT_LANGUAGE"] = language
    try:
        from voice.stt_engine import STTEngine
        result = STTEngine().transcribe(audio_bytes)
        return result.text
    except Exception:
        return ""


# ── TTS helper ──────────────────────────────────────────────────────────────
def _tts(text: str, language: str = "en-IN") -> bytes | None:
    os.environ["TTS_LANGUAGE"] = language
    # Try Sarvam AI (primary)
    try:
        from voice.tts_engine import TTSEngine
        r = TTSEngine().synthesise(text, language=language)
        if not r.is_empty:
            return r.audio_bytes
    except Exception:
        pass
    # Fallback: gTTS
    try:
        import io as _io
        from gtts import gTTS
        buf = _io.BytesIO()
        gTTS(text=text, lang="hi" if language == "hi-IN" else "en",
             tld="co.in" if language == "en-IN" else "com", slow=False).write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


# ── JS helpers ───────────────────────────────────────────────────────────────
def _play_and_listen_js(audio_bytes: bytes, turn_id: str):
    import base64
    b64 = base64.b64encode(audio_bytes).decode()
    fmt = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mpeg"
    components.html(f"""
    <script>
    (function() {{
        var TURN = '{turn_id}';
        var pdoc = window.parent.document;
        if (window.parent.__vadTurn === TURN) return;
        window.parent.__vadTurn = TURN;
        if (typeof window.parent.__vadStop === 'function') {{ window.parent.__vadStop(); }}

        var ONSET_LEVEL = 18, SILENCE_LEVEL = 12, MIN_SPEECH_MS = 200, SILENCE_MS = 2000, NO_INPUT_MS = 10000;
        var vadStream = null, audioCtx = null, noInputTimer = null, checkRAF = null, micStarted = false;

        function setStatus(msg, color) {{
            var el = pdoc.getElementById('vad-live-status');
            if (!el) return;
            el.textContent = msg;
            el.style.color = color || '';
            el.style.borderColor = color ? color.replace('1)', '0.35)') : '';
        }}
        function getRecordBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Record"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (inp) {{ var fb = inp.querySelector('button'); if (fb) return fb; }}
            return null;
        }}
        function getStopBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Stop recording"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (inp) {{ var btns = inp.querySelectorAll('button'); if (btns.length > 1) return btns[btns.length-1]; if (btns.length === 1) return btns[0]; }}
            return null;
        }}
        function stopRecordingAndVAD() {{
            clearTimeout(noInputTimer);
            if (checkRAF) {{ cancelAnimationFrame(checkRAF); checkRAF = null; }}
            if (vadStream) {{ vadStream.getTracks().forEach(function(t){{ t.stop(); }}); vadStream = null; }}
            if (audioCtx) {{ try {{ audioCtx.close(); }} catch(e) {{}} audioCtx = null; }}
            window.parent.__vadStop = null;
            if (micStarted) {{
                micStarted = false;
                setStatus('Processing your response…', 'rgba(201,168,76,1)');
                var btn = getStopBtn();
                if (btn) btn.click();
            }}
        }}
        window.parent.__vadStop = stopRecordingAndVAD;

        function rms(data) {{
            var s = 0;
            for (var i = 0; i < data.length; i++) s += data[i] * data[i];
            return Math.sqrt(s / data.length);
        }}
        function runVADOnStream(stream) {{
            vadStream = stream;
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            var analyser = audioCtx.createAnalyser();
            analyser.fftSize = 512;
            audioCtx.createMediaStreamSource(stream).connect(analyser);
            var data = new Uint8Array(analyser.frequencyBinCount);
            var CALIB_MS = 1500, calibSamples = [];
            var onsetLevel = ONSET_LEVEL, silenceLevel = SILENCE_LEVEL;
            setStatus('📡 Calibrating mic…', 'rgba(201,168,76,0.7)');
            function calibrate() {{
                if (!vadStream) return;
                analyser.getByteTimeDomainData(data);
                calibSamples.push(rms(data));
                if (Date.now() - calibStart < CALIB_MS) {{ checkRAF = requestAnimationFrame(calibrate); }}
                else {{
                    calibSamples.sort(function(a,b){{return a-b;}});
                    var ambient = calibSamples[Math.floor(calibSamples.length / 2)];
                    onsetLevel   = Math.max(ONSET_LEVEL,   ambient * 3.0);
                    silenceLevel = Math.max(SILENCE_LEVEL, ambient * 1.8);
                    setStatus('🎙 Listening — speak now', 'rgba(34,197,94,1)');
                    noInputTimer = setTimeout(function() {{ if (!hasSpeech) {{ setStatus('No speech detected…', 'rgba(239,68,68,1)'); stopRecordingAndVAD(); }} }}, NO_INPUT_MS);
                    checkRAF = requestAnimationFrame(check);
                }}
            }}
            var hasSpeech = false, speechStart = null, silenceStart = null;
            function check() {{
                if (!vadStream) return;
                analyser.getByteTimeDomainData(data);
                var level = rms(data);
                if (!hasSpeech) {{
                    if (level > onsetLevel) {{
                        if (!speechStart) speechStart = Date.now();
                        else if (Date.now() - speechStart >= MIN_SPEECH_MS) {{ hasSpeech = true; silenceStart = null; setStatus('🗣 User speaking…', 'rgba(34,197,94,1)'); clearTimeout(noInputTimer); }}
                    }} else {{ speechStart = null; }}
                }} else {{
                    if (level < silenceLevel) {{
                        if (!silenceStart) {{ silenceStart = Date.now(); setStatus('🗣 User speaking… (paused)', 'rgba(201,168,76,1)'); }}
                        else if (Date.now() - silenceStart > SILENCE_MS) {{ stopRecordingAndVAD(); return; }}
                    }} else {{ silenceStart = null; setStatus('🗣 User speaking…', 'rgba(34,197,94,1)'); }}
                }}
                checkRAF = requestAnimationFrame(check);
            }}
            var calibStart = Date.now();
            checkRAF = requestAnimationFrame(calibrate);
        }}
        var _micRetries = 0;
        function startMicAndVAD() {{
            var btn = getRecordBtn();
            if (!btn) {{
                if (++_micRetries < 50) {{ setTimeout(startMicAndVAD, 150); return; }}
                setStatus('❌ Mic unavailable', 'rgba(239,68,68,1)'); return;
            }}
            setStatus('🎙 Mic starting…', 'rgba(34,197,94,0.7)');
            micStarted = true;
            btn.click();
            navigator.mediaDevices.getUserMedia({{ audio: true, video: false }})
            .then(function(stream) {{ runVADOnStream(stream); }})
            .catch(function(e) {{ setStatus('❌ Mic permission denied', 'rgba(239,68,68,1)'); }});
        }}

        var b64  = '{b64}';
        var mime = '{fmt}';
        var raw  = atob(b64);
        var buf  = new Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
        var blob = new Blob([buf], {{ type: mime }});
        var url  = URL.createObjectURL(blob);
        var audio = new Audio(url);
        setStatus('🔊 Agent speaking…', 'rgba(201,168,76,1)');
        audio.addEventListener('ended', function() {{
            URL.revokeObjectURL(url);
            setTimeout(startMicAndVAD, 50);
        }}, {{ once: true }});
        audio.play().catch(function(e) {{
            setStatus('⚠ Audio blocked — speak now', 'rgba(239,68,68,1)');
            URL.revokeObjectURL(url);
            startMicAndVAD();
        }});
    }})();
    </script>
    """, height=0)


def _start_listen_js(turn_id: str):
    components.html(f"""
    <script>
    (function() {{
        var TURN = '{turn_id}_listen';
        var pdoc = window.parent.document;
        if (window.parent.__vadTurn === TURN) return;
        window.parent.__vadTurn = TURN;
        if (typeof window.parent.__vadStop === 'function') {{ window.parent.__vadStop(); }}
        var ONSET_LEVEL = 18, SILENCE_LEVEL = 12, MIN_SPEECH_MS = 200, SILENCE_MS = 2000, NO_INPUT_MS = 10000;
        var vadStream = null, audioCtx = null, noInputTimer = null, checkRAF = null, micStarted = false;
        function setStatus(msg, color) {{
            var el = pdoc.getElementById('vad-live-status');
            if (!el) return;
            el.textContent = msg; el.style.color = color || '';
        }}
        function getRecordBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Record"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (inp) {{ var fb = inp.querySelector('button'); if (fb) return fb; }}
            return null;
        }}
        function getStopBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Stop recording"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (inp) {{ var btns = inp.querySelectorAll('button'); if (btns.length > 1) return btns[btns.length-1]; if (btns.length === 1) return btns[0]; }}
            return null;
        }}
        function stop() {{
            clearTimeout(noInputTimer);
            if (checkRAF) {{ cancelAnimationFrame(checkRAF); checkRAF = null; }}
            if (vadStream) {{ vadStream.getTracks().forEach(function(t){{ t.stop(); }}); vadStream = null; }}
            if (audioCtx) {{ try{{ audioCtx.close(); }}catch(e){{}} audioCtx = null; }}
            window.parent.__vadStop = null;
            if (micStarted) {{ setStatus('Processing…', 'rgba(201,168,76,1)'); var btn = getStopBtn(); if (btn) btn.click(); micStarted = false; }}
        }}
        window.parent.__vadStop = stop;
        function rms(data) {{ var s=0; for(var i=0;i<data.length;i++) s+=data[i]*data[i]; return Math.sqrt(s/data.length); }}
        function runVADOnStream(stream) {{
            vadStream = stream;
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            var analyser = audioCtx.createAnalyser(); analyser.fftSize = 512;
            audioCtx.createMediaStreamSource(stream).connect(analyser);
            var data = new Uint8Array(analyser.frequencyBinCount);
            var CALIB_MS=1500, calibSamples=[], onsetLevel=ONSET_LEVEL, silenceLevel=SILENCE_LEVEL;
            setStatus('📡 Calibrating mic…', 'rgba(201,168,76,0.7)');
            function calibrate() {{
                if (!vadStream) return;
                analyser.getByteTimeDomainData(data); calibSamples.push(rms(data));
                if (Date.now()-calibStart < CALIB_MS) {{ checkRAF=requestAnimationFrame(calibrate); }}
                else {{
                    calibSamples.sort(function(a,b){{return a-b;}});
                    var ambient=calibSamples[Math.floor(calibSamples.length/2)];
                    onsetLevel=Math.max(ONSET_LEVEL,ambient*3.0); silenceLevel=Math.max(SILENCE_LEVEL,ambient*1.8);
                    setStatus('🎙 Listening — speak now','rgba(34,197,94,1)');
                    noInputTimer=setTimeout(function(){{if(!hasSpeech){{setStatus('No speech…','rgba(239,68,68,1)');stop();}}}},NO_INPUT_MS);
                    checkRAF=requestAnimationFrame(check);
                }}
            }}
            var hasSpeech=false, speechStart=null, silenceStart=null;
            function check() {{
                if (!vadStream) return; analyser.getByteTimeDomainData(data); var level=rms(data);
                if (!hasSpeech) {{
                    if (level>onsetLevel) {{ if(!speechStart) speechStart=Date.now(); else if(Date.now()-speechStart>=MIN_SPEECH_MS){{ hasSpeech=true; setStatus('🗣 User speaking…','rgba(34,197,94,1)'); clearTimeout(noInputTimer); }} }}
                    else {{ speechStart=null; }}
                }} else {{
                    if (level<silenceLevel) {{ if(!silenceStart){{silenceStart=Date.now();setStatus('🗣 User speaking… (paused)','rgba(201,168,76,1)');}} else if(Date.now()-silenceStart>SILENCE_MS){{stop();return;}} }}
                    else {{ silenceStart=null; setStatus('🗣 User speaking…','rgba(34,197,94,1)'); }}
                }}
                checkRAF=requestAnimationFrame(check);
            }}
            var calibStart=Date.now(); checkRAF=requestAnimationFrame(calibrate);
        }}
        var _retry=0;
        function startMic() {{
            var btn=getRecordBtn();
            if (!btn) {{ if(++_retry<50){{setTimeout(startMic,150);return;}} setStatus('❌ Mic unavailable','rgba(239,68,68,1)'); return; }}
            setStatus('🎙 Mic starting…','rgba(34,197,94,0.7)'); micStarted=true; btn.click();
            navigator.mediaDevices.getUserMedia({{audio:true,video:false}})
            .then(function(stream){{runVADOnStream(stream);}})
            .catch(function(e){{setStatus('❌ Mic permission denied','rgba(239,68,68,1)');}});
        }}
        startMic();
    }})();
    </script>
    """, height=0)


# ── Session state ─────────────────────────────────────────────────────────────
def _init_state():
    for k, v in {
        "va_started": False, "va_ctx": None, "va_fsm": None,
        "va_lang": "en-IN", "va_agent_speech": "", "va_user_text": "",
        "_va_tts_hash": "", "_va_tts_audio": None,
        "_va_tts_played": "", "_va_last_audio_hash": "",
        "_va_backend_status": "",
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

_lang = st.session_state.va_lang
os.environ["TTS_LANGUAGE"] = _lang
os.environ["STT_LANGUAGE"] = _lang


# ── Process user turn ─────────────────────────────────────────────────────────
def _process(user_text: str):
    from dialogue.intent_router import IntentRouter
    from dialogue.compliance_guard import ComplianceGuard
    from booking.pii_scrubber import scrub_pii

    # Layer 1: PII scrub (mirrors phase4_voice_pillar_b/voice_agent.py step())
    pii_result = scrub_pii(user_text)
    clean_input = pii_result.cleaned_text
    if pii_result.pii_found:
        st.session_state["_va_backend_status"] = "⚠ PII detected and redacted…"

    fsm = st.session_state.va_fsm
    ctx = st.session_state.va_ctx
    try:
        st.session_state["_va_backend_status"] = "Understanding intent…"
        llm_resp = IntentRouter().route(clean_input, ctx)
    except Exception as exc:
        st.error(f"Routing error: {exc}")
        return
    ctx, speech = fsm.process_turn(ctx, clean_input, llm_resp)
    # MCP dispatch happens inside fsm.process_turn (_dispatch_mcp)
    # — ctx.calendar_hold_created / ctx.notes_appended / ctx.email_drafted / ctx.secure_url
    #   are all set by the FSM before returning.

    # Layer 3: Compliance guard
    if speech:
        speech = ComplianceGuard().check_and_gate(speech)

    # Clear the "Processing…" spinner now that FSM + MCP are done
    st.session_state["_va_backend_status"] = ""
    st.session_state.va_ctx = ctx
    if not speech:
        speech = ("I didn't catch that — could you say that again?"
                  if _lang == "en-IN"
                  else "मुझे सुनाई नहीं दिया — क्या आप दोबारा कह सकते हैं?")
    st.session_state.va_agent_speech = speech
    import time as _t
    st.session_state["_va_tts_played"] = f"_reset_{_t.time()}"


# ── Site header ───────────────────────────────────────────────────────────────
_hi = _lang == "hi-IN"
st.markdown(f"""
<div class="dsa-header">
  <div class="dsa-logo-wrap">
    <div class="dsa-logo-icon">📈</div>
    <div>
      <div class="dsa-logo-text">Dalal Street Advisors</div>
      <div class="dsa-logo-sub">SEBI Registered · IA-0000347</div>
    </div>
  </div>
  <nav class="dsa-nav">
    <a href="#">{"Services" if not _hi else "सेवाएँ"}</a>
    <a href="#">{"About" if not _hi else "हमारे बारे में"}</a>
    <a href="#">{"Contact" if not _hi else "संपर्क"}</a>
    <a href="/">{"← Back to Suite" if not _hi else "← वापस"}</a>
  </nav>
</div>
""", unsafe_allow_html=True)

# ── PRE-CALL LANDING ──────────────────────────────────────────────────────────
if not st.session_state.va_started:
    _top_theme_raw = st.session_state.get("top_theme", "")
    if not _top_theme_raw:
        try:
            import json as _json
            _pd = _json.loads((_root_dir / "data" / "pulse_latest.json").read_text())
            _t3 = _pd.get("top_3_themes", [])
            if _t3:
                _top_theme_raw = _t3[0]
                st.session_state["top_theme"] = _top_theme_raw
        except Exception:
            pass

    # Language toggle
    st.markdown("""
    <div style="background:rgba(10,12,20,0.85);border-bottom:1px solid rgba(255,255,255,0.05);
         display:flex;justify-content:flex-end;align-items:center;padding:6px 48px;gap:8px;">
      <span style="font-size:0.72rem;color:#6B6358;letter-spacing:0.05em;text-transform:uppercase;">Language</span>
    </div>
    """, unsafe_allow_html=True)
    _lang_col_l, _lang_col_r = st.columns([9, 1])
    with _lang_col_r:
        lang_lbl = st.radio("", ["EN", "HI"], horizontal=True,
                            key="va_lang_radio", label_visibility="collapsed")
    st.session_state.va_lang = "hi-IN" if lang_lbl == "HI" else "en-IN"
    _lang = st.session_state.va_lang
    _hi   = _lang == "hi-IN"

    _top_theme_chip_en = (
        f'<span style="background:rgba(201,168,76,0.18);border:1px solid rgba(201,168,76,0.5);'
        f'border-radius:20px;padding:2px 10px;font-size:0.78rem;color:#C9A84C;white-space:nowrap;">'
        f'📌 Top theme this week: {_top_theme_raw}</span> '
    ) if _top_theme_raw else ""

    _topic_list_en = (
        f"{_top_theme_chip_en}"
        "KYC and Onboarding, SIP and Mandates, Statements and Tax, "
        "Withdrawals and Timelines, or Account Changes and Nominee Updates."
    )
    _topic_list_hi = "KYC और ऑनबोर्डिंग, SIP और मैंडेट, विवरण और टैक्स, निकासी, या खाता बदलाव।"

    st.markdown(f"""
    <div class="lp-wrap">
      <div class="lp-badge">
        <span class="lp-badge-dot"></span>
        {"AI-Powered · SEBI Registered · Live Scheduling" if not _hi else "AI-संचालित · SEBI पंजीकृत · लाइव शेड्यूलिंग"}
      </div>
      <div class="lp-title">{"Advisor Scheduling <br><span>Voice Agent</span>" if not _hi else "सलाहकार शेड्यूलिंग <br><span>वॉइस एजेंट</span>"}</div>
      <div class="lp-sub">
        {"Book a 15-minute consultation with SEBI-registered advisors — "
         if not _hi else
         "SEBI-पंजीकृत सलाहकारों के साथ 15 मिनट की परामर्श बुक करें — "}
        {_topic_list_en if not _hi else _topic_list_hi}
        {" Just speak." if not _hi else " बस बोलें।"}
      </div>
    </div>
    """, unsafe_allow_html=True)

    _hero_l, _hero_c, _hero_r = st.columns([3, 2, 3])
    with _hero_c:
        if st.button("🎙  Start Advisor Call", type="primary",
                     use_container_width=True, key="va_hero_cta"):
            from dialogue.fsm import DialogueFSM
            fsm = DialogueFSM()
            ctx, greeting = fsm.start()
            st.session_state.va_fsm          = fsm
            st.session_state.va_ctx          = ctx
            st.session_state.va_started      = True
            st.session_state.va_agent_speech = greeting
            st.session_state["_va_tts_hash"]   = ""
            st.session_state["_va_tts_played"] = ""
            st.rerun()

    st.markdown(f"""
    <div style="max-width:440px;margin:0 auto 24px;">
      <div class="stat-strip">
        <div class="stat-cell"><div class="stat-val">₹2,400 Cr</div><div class="stat-lbl">{"AUA" if not _hi else "AUA"}</div></div>
        <div class="stat-cell"><div class="stat-val">14,000+</div><div class="stat-lbl">{"Clients" if not _hi else "ग्राहक"}</div></div>
        <div class="stat-cell"><div class="stat-val">4.8 ★</div><div class="stat-lbl">{"Rating" if not _hi else "रेटिंग"}</div></div>
      </div>
      <div class="disclaimer-box">
        <strong>{"SEBI Disclaimer:" if not _hi else "SEBI अस्वीकरण:"}</strong>
        {" Advisors provide informational guidance only — not investment advice. No PII collected on this call."
         if not _hi else
         " सलाहकार केवल जानकारी देते हैं, निवेश सलाह नहीं। कॉल पर कोई व्यक्तिगत जानकारी नहीं ली जाती।"}
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.stop()


# ── ACTIVE CALL ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dsa-header" style="position:relative;">
  <div class="dsa-logo-wrap">
    <div class="dsa-logo-icon">📈</div>
    <div>
      <div class="dsa-logo-text">Dalal Street Advisors</div>
      <div class="dsa-logo-sub">SEBI Registered · IA-0000347</div>
    </div>
  </div>
  <div style="font-size:0.82rem;color:var(--gold-dim);letter-spacing:0.04em;">
    {"● Live Call in Progress" if _lang == "en-IN" else "● कॉल जारी है"}
  </div>
</div>
<div class="call-page-wrap">
""", unsafe_allow_html=True)

ctx    = st.session_state.va_ctx
speech = st.session_state.va_agent_speech

_is_terminal   = ctx and ctx.current_state.is_terminal()
_is_complete   = ctx and ctx.current_state.name == "BOOKING_COMPLETE"
_is_waitlisted = ctx and ctx.current_state.name == "WAITLIST_CONFIRMED"
_agent_turn    = bool(speech) and not _is_terminal and not _is_complete and not _is_waitlisted


# ── Booking Complete ──────────────────────────────────────────────────────────
if _is_complete:
    # Clear backend status immediately — no more "Processing your response"
    st.session_state["_va_backend_status"] = ""

    _bc_code    = ctx.booking_code or ""
    _secure_url = getattr(ctx, "secure_url", "") or ""

    # Build contact-details link HTML
    _link_html = (
        f'<div class="booking-link">'
        f'📎 <strong>Provide your contact details</strong> to receive a confirmation email:<br>'
        f'<a href="{_secure_url}" target="_blank">{_secure_url}</a>'
        f'</div>'
    ) if _secure_url else ""

    # Build MCP status pills
    _cal_ok   = getattr(ctx, "calendar_hold_created", None)
    _sheet_ok = getattr(ctx, "notes_appended", None)
    _email_ok = getattr(ctx, "email_drafted", None)
    def _pill(icon, label, ok):
        if ok is None:
            return ""
        cls = "mcp-ok" if ok else "mcp-err"
        sym = "✅" if ok else "❌"
        return f'<span class="mcp-pill {cls}">{sym} {icon} {label}</span>'
    _mcp_html = (
        f'<div class="mcp-status-row">'
        f'{_pill("📅", "Calendar", _cal_ok)}'
        f'{_pill("📊", "Sheets",   _sheet_ok)}'
        f'{_pill("📧", "Email",    _email_ok)}'
        f'</div>'
    ) if any(x is not None for x in [_cal_ok, _sheet_ok, _email_ok]) else ""

    st.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;padding:48px 20px 20px;">
      <div class="booking-success">
        <div class="booking-success-icon">✅</div>
        <div class="booking-success-title">Booking Confirmed!</div>
        <div style="color:#a7f3d0;font-size:0.9rem;margin-bottom:8px;">Your booking code is</div>
        <div class="booking-code-badge">{_bc_code}</div>
        <div style="color:#6ee7b7;font-size:0.88rem;margin-bottom:4px;">
          A tentative calendar hold has been created.<br>
          An advisor will reach out to confirm.
        </div>
        {_link_html}
        {_mcp_html}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Play final audio — no mic/VAD after booking complete
    if speech:
        _th = hashlib.md5(speech.encode()).hexdigest()
        if st.session_state["_va_tts_hash"] != _th:
            ab = _tts(speech, language=_lang)
            st.session_state["_va_tts_hash"]  = _th
            st.session_state["_va_tts_audio"] = ab
        else:
            ab = st.session_state["_va_tts_audio"]
        if ab and st.session_state["_va_tts_played"] != _th:
            st.session_state["_va_tts_played"] = _th
            import base64 as _b64
            _b64str = _b64.b64encode(ab).decode()
            _fmt = "audio/wav" if ab[:4] == b"RIFF" else "audio/mpeg"
            components.html(f"""<script>
            (function(){{var raw=atob('{_b64str}'),buf=new Uint8Array(raw.length);
            for(var i=0;i<raw.length;i++)buf[i]=raw.charCodeAt(i);
            var url=URL.createObjectURL(new Blob([buf],{{type:'{_fmt}'}}));
            var a=new Audio(url);a.play().catch(function(){{}});
            a.addEventListener('ended',function(){{URL.revokeObjectURL(url);}},{{once:true}});
            }})();</script>""", height=0)

    _, _nb, _ = st.columns([2, 3, 2])
    with _nb:
        if st.button("📞  New Call", type="primary", use_container_width=True, key="va_new_call_complete"):
            for k in ["va_started","va_ctx","va_fsm","va_agent_speech","va_user_text","_va_tts_hash",
                      "_va_tts_audio","_va_tts_played","_va_last_audio_hash"]:
                st.session_state.pop(k, None)
            _init_state()
            st.rerun()
    st.stop()


# ── Waitlist Confirmed ────────────────────────────────────────────────────────
if _is_waitlisted:
    st.session_state["_va_backend_status"] = ""
    _wl_code    = ctx.waitlist_code or ""
    _wl_url     = getattr(ctx, "secure_url", "") or ""
    _wl_link_html = (
        f'<div class="booking-link">'
        f'📎 <strong>Submit your email</strong> to get notified when your slot opens:<br>'
        f'<a href="{_wl_url}" target="_blank">{_wl_url}</a>'
        f'</div>'
    ) if _wl_url else ""
    st.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;padding:48px 20px 20px;">
      <div class="booking-success" style="border-color:rgba(34,197,94,0.30);">
        <div class="booking-success-icon">🔔</div>
        <div class="booking-success-title" style="color:#4ade80;">Added to Waitlist!</div>
        <div style="color:#a7f3d0;font-size:0.9rem;margin-bottom:8px;">Your waitlist code is</div>
        <div class="booking-code-badge" style="color:#4ade80;">{_wl_code}</div>
        <div style="color:#6ee7b7;font-size:0.88rem;margin-bottom:4px;">
          We'll notify you when a matching slot opens.
        </div>
        {_wl_link_html}
      </div>
    </div>
    """, unsafe_allow_html=True)
    _, _nb2, _ = st.columns([2, 3, 2])
    with _nb2:
        if st.button("📞  New Call", type="primary", use_container_width=True, key="va_new_call_wl"):
            for k in ["va_started","va_ctx","va_fsm","va_agent_speech","va_user_text","_va_tts_hash",
                      "_va_tts_audio","_va_tts_played","_va_last_audio_hash"]:
                st.session_state.pop(k, None)
            _init_state()
            st.rerun()
    st.stop()


# ── Call ended ────────────────────────────────────────────────────────────────
if _is_terminal:
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;padding:60px 20px;">
      <div style="font-size:3.5rem;margin-bottom:16px;">📵</div>
      <div style="font-size:1.3rem;font-weight:700;color:#f3f0ff;margin-bottom:8px;">Call Ended</div>
      <div style="color:#a78bfa;font-size:0.9rem;">Thank you for using the Advisor Scheduling Agent.</div>
    </div>
    """, unsafe_allow_html=True)
    _, _nb3, _ = st.columns([2, 3, 2])
    with _nb3:
        if st.button("📞  New Call", type="primary", use_container_width=True, key="va_new_call_end"):
            for k in ["va_started","va_ctx","va_fsm","va_agent_speech","va_user_text","_va_tts_hash",
                      "_va_tts_audio","_va_tts_played","_va_last_audio_hash"]:
                st.session_state.pop(k, None)
            _init_state()
            st.rerun()
    st.stop()


# ── Live call screen ──────────────────────────────────────────────────────────
_tts_ready = (speech and
              st.session_state["_va_tts_hash"] == hashlib.md5(speech.encode()).hexdigest())
if _agent_turn and _tts_ready:
    _dot_cls    = "gold"
    _ring_class = "speaking"
    _status     = "Speaking…" if _lang == "en-IN" else "बोल रहे हैं…"
elif _agent_turn and not _tts_ready:
    _dot_cls    = "dim"
    _ring_class = "idle"
    _status     = "One moment…" if _lang == "en-IN" else "एक पल…"
else:
    _dot_cls    = "green"
    _ring_class = "listening"
    _status     = "Listening…" if _lang == "en-IN" else "सुन रहे हैं…"

_caption = speech if speech else ""
_user_text = st.session_state.get("va_user_text", "")
_user_caption = _user_text if _user_text else ""

_transcript_block = (
    f'<div style="margin-top:10px;padding:8px 14px;border-radius:8px;'
    f'background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
    f'text-align:left;max-width:440px;margin-left:auto;margin-right:auto;">'
    f'<div style="font-size:0.7rem;color:#6B6358;letter-spacing:0.06em;'
    f'text-transform:uppercase;margin-bottom:6px;">Transcript</div>'
    f'<div style="font-size:0.82rem;margin-bottom:4px;max-height:110px;overflow-y:auto;">'
    f'<span style="color:#C9A84C;font-weight:600;vertical-align:top;">Agent&nbsp;</span>'
    f'<span style="color:#D4CFC9;white-space:pre-wrap;">{_caption if _caption else "—"}</span></div>'
    f'<div style="font-size:0.82rem;max-height:55px;overflow-y:auto;">'
    f'<span style="color:#7EB6FF;font-weight:600;vertical-align:top;">You&nbsp;&nbsp;&nbsp;</span>'
    f'<span style="color:#D4CFC9;">{_user_caption if _user_caption else "—"}</span></div>'
    f'</div>'
) if (_caption or _user_caption) else ""

st.markdown(f"""
<div class="call-wrap">
  <div class="ring-outer {_ring_class}">
    <div class="caller-avatar">🤖</div>
  </div>
  <div class="caller-name">Advisor Agent</div>
  <div class="caller-firm">{"Dalal Street Advisors · AI Scheduling" if _lang == "en-IN" else "Dalal Street Advisors · AI शेड्यूलिंग"}</div>
  <div class="status-pill">
    <span class="s-dot {_dot_cls}"></span>
    {_status}
  </div>
  <div class="agent-caption">{_caption if _caption else "&nbsp;"}</div>
  {_transcript_block}
  <div class="vad-live-wrap">
    <div id="vad-live-status" class="vad-live-status">&nbsp;</div>
  </div>
  <div class="backend-status">{st.session_state.get("_va_backend_status","") or "&nbsp;"}</div>
</div>
""", unsafe_allow_html=True)

# ── TTS + VAD ─────────────────────────────────────────────────────────────────
if speech:
    text_hash  = hashlib.md5(speech.encode()).hexdigest()
    _turn_cnt  = ctx.turn_count if ctx else 0
    turn_key   = hashlib.md5(f"{_turn_cnt}:{text_hash}".encode()).hexdigest()[:16]

    if st.session_state["_va_tts_hash"] != text_hash:
        st.session_state["_va_backend_status"] = "Preparing audio…"
        audio_bytes = _tts(speech, language=_lang)
        st.session_state["_va_backend_status"] = ""
        st.session_state["_va_tts_hash"]  = text_hash
        st.session_state["_va_tts_audio"] = audio_bytes
    else:
        audio_bytes = st.session_state["_va_tts_audio"]

    if st.session_state["_va_tts_played"] != turn_key:
        st.session_state["_va_tts_played"] = turn_key
        if audio_bytes:
            _play_and_listen_js(audio_bytes, turn_id=turn_key)
        else:
            _start_listen_js(turn_id=turn_key)

# ── Microphone input ──────────────────────────────────────────────────────────
_mic_lbl = "mic" if _lang == "en-IN" else "mic-hi"
audio_input = st.audio_input(_mic_lbl, key="va_audio_input", label_visibility="hidden")
if audio_input is not None:
    _ab    = audio_input.read()
    _ahash = hashlib.md5(_ab).hexdigest()
    if st.session_state.get("_va_last_audio_hash") != _ahash:
        st.session_state["_va_last_audio_hash"] = _ahash
        if len(_ab) < 8_000:
            _process("")
        else:
            st.session_state["_va_backend_status"] = "Transcribing speech…"
            transcript = _stt(_ab, language=_lang)
            _repeat_words = [
                "repeat","again","say that again","pardon","come again",
                "what","huh","sorry","excuse me","once more",
                "kya","dobara","phir se","samjha nahi","suna nahi",
            ]
            _t_lower = transcript.lower().strip()
            _is_repeat = any(w in _t_lower for w in _repeat_words) and len(_t_lower) < 40
            if _is_repeat:
                st.session_state["_va_tts_played"] = ""
            else:
                st.session_state["va_user_text"] = transcript or ""
                _process(transcript or "")
        st.rerun()

# ── End call button ───────────────────────────────────────────────────────────
st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
_, _ec, _ = st.columns([3, 2, 3])
with _ec:
    if st.button("End Call", type="secondary", use_container_width=True, key="va_end_call"):
        for k in ["va_started","va_ctx","va_fsm","va_agent_speech","_va_tts_hash",
                  "_va_tts_audio","_va_tts_played","_va_last_audio_hash"]:
            st.session_state.pop(k, None)
        _init_state()
        st.rerun()

st.markdown("""
</div>
<div style="background:#07080F;border-top:1px solid rgba(255,255,255,0.06);
     padding:20px 48px;text-align:center;margin-top:32px;">
  <div style="font-size:0.75rem;color:#4A4540;line-height:1.7;">
    © 2025 <span style="color:#6B6358;">Dalal Street Advisors Pvt. Ltd.</span> ·
    SEBI IA Reg. No. IA-0000347 ·
    No personal information is collected on this call.
  </div>
</div>
""", unsafe_allow_html=True)
