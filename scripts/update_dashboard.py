"""Reads capstone pipeline JSONs and bakes them into data/dashboard.html as JS constants.
Adapted from M2 Phase6_Web_App/update_dashboard.py.

Run automatically by scripts/run_review_pipeline.py after the pipeline completes.
Manual usage: python scripts/update_dashboard.py
"""
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "data" / "dashboard.html"
DATA = ROOT / "data"

_CAT_COLORS = ["#4ade80", "#60a5fa", "#f59e0b", "#f472b6", "#a78bfa"]
_BASE_VOLUMES = [120, 27, 24, 16, 15]


def _escape_js(text: str) -> str:
    return text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def run() -> None:
    pulse    = json.loads((DATA / "pulse_latest.json").read_text())
    analytics = json.loads((DATA / "analytics_latest.json").read_text()) if (DATA / "analytics_latest.json").exists() else {}
    fee      = json.loads((DATA / "fee_latest.json").read_text()) if (DATA / "fee_latest.json").exists() else {}

    top_3         = pulse.get("top_3_themes", [])
    themes        = pulse.get("themes", top_3)
    weekly_note   = pulse.get("weekly_note", "")
    action_ideas  = pulse.get("action_ideas", [])
    quotes        = pulse.get("quotes", [])
    today_str     = date.today().strftime("%B %-d, %Y")

    # ── Build email draft (Section 1: Pulse + Section 2: Fee) ────────────────
    bullet_lines  = "\n".join(fee.get("bullets", []))
    source_lines  = ", ".join(fee.get("sources", []))
    email_draft = (
        f"WEEKLY INDMONEY PRODUCT PULSE\n{'='*60}\n"
        f"Date    : {today_str}\n{'='*60}\n\n"
        f"SECTION 1 — WEEKLY PULSE\n{'─'*26}\n"
        f"Top 3 Themes: {', '.join(top_3)}\n\n"
        f"User Quotes:\n" + "\n".join(f'  "{q}"' for q in quotes) + "\n\n"
        f"Weekly Note:\n{weekly_note}\n\n"
        f"Action Ideas:\n" + "\n".join(f"{i+1}. {a}" for i, a in enumerate(action_ideas)) + "\n\n"
        f"SECTION 2 — FEE EXPLAINER\n{'─'*26}\n"
        f"{fee.get('scenario', 'SBI Mutual Funds — Exit Load')}\n\n"
        f"{bullet_lines}\n\n"
        f"Sources: {source_lines}\n"
        f"Last checked: {fee.get('checked', today_str)}\n\n"
        f"{'='*60}\n[DRAFT — Pending human review before sending]"
    )

    # ── Append entry to pulse_notes.md ────────────────────────────────────────
    notes_file = DATA / "pulse_notes.md"
    new_entry = (
        f"## Week of {today_str}\n\n"
        f"### Weekly Note\n{weekly_note}\n\n"
        f"### Top 3 Themes\n" + "\n".join(f"- {t}" for t in top_3) + "\n\n"
        f"### Action Ideas\n" + "\n".join(f"{i+1}. {a}" for i, a in enumerate(action_ideas)) + "\n\n"
        f"---\n\n"
    )
    existing = notes_file.read_text(encoding="utf-8") if notes_file.exists() else ""
    notes_file.write_text(new_entry + existing, encoding="utf-8")
    notes_md = notes_file.read_text(encoding="utf-8")

    # ── Convert analytics to M2 dashboard format ─────────────────────────────
    # Keywords: capstone {word,count,color} → M2 {w,n,c}
    keywords_m2 = [
        {"w": kw["word"], "n": kw["count"], "c": kw["color"]}
        for kw in analytics.get("keywords", [])
    ]

    # Categories: derived from themes with simulated volumes
    total_vol = sum(_BASE_VOLUMES[:min(len(themes), 5)])
    categories_data = [
        {
            "name":  t,
            "count": _BASE_VOLUMES[i] if i < len(_BASE_VOLUMES) else 10,
            "pct":   round((_BASE_VOLUMES[i] if i < len(_BASE_VOLUMES) else 10) / total_vol * 100, 1),
            "color": _CAT_COLORS[i % len(_CAT_COLORS)],
        }
        for i, t in enumerate(themes[:5])
    ]

    # Negative reviews: capstone {text,rating} → M2 {name,stars,text,tags}
    neg_reviews_m2 = [
        {
            "name":  "App User",
            "stars": max(1, min(5, int(float(nr.get("rating", 1))))),
            "text":  nr.get("text", ""),
            "tags":  [next((t for t in themes if any(w.lower() in nr.get("text","").lower() for w in t.split())), themes[0] if themes else "general")],
        }
        for nr in analytics.get("negative_reviews", [])
    ]

    # FEE_DATA in M2 format
    scenario_raw = fee.get("scenario", "exit_load")
    _sname = scenario_raw.replace("_", " ").title() if "_" in scenario_raw else scenario_raw
    if not any(w in _sname.lower() for w in ("explainer", "fee", "load", "charge")):
        _sname += " — Fee Explainer"
    fee_data_m2 = {
        "scenario_name":      _sname,
        "explanation_bullets": fee.get("bullets", []),
        "source_links":       fee.get("sources", []),
        "last_checked":       fee.get("checked", today_str),
    }

    # PULSE_DATA (already correct shape)
    pulse_data = {
        "themes":       themes,
        "top_3_themes": top_3,
        "quotes":       quotes,
        "weekly_note":  weekly_note,
        "action_ideas": action_ideas,
    }

    # ANALYTICS_META
    analytics_meta = {
        "review_count": analytics.get("total", analytics.get("review_count", pulse.get("review_count", 0))),
        "sentiment":    analytics.get("sentiment", {}),
        "rating_dist":  analytics.get("rating_dist", {}),
    }

    # ── Patch dashboard.html ──────────────────────────────────────────────────
    html = DASHBOARD.read_text(encoding="utf-8")

    # Always point the email API at the local background server
    html = re.sub(r"const API = '[^']*';", "const API = 'http://localhost:8510';", html)

    html = re.sub(
        r"(const EMAIL_DRAFT = `)[\s\S]*?(`;)",
        lambda _: f"const EMAIL_DRAFT = `{_escape_js(email_draft)}`;",
        html,
    )
    html = re.sub(
        r"(const NOTES_MD = `)[\s\S]*?(`;)",
        lambda _: f"const NOTES_MD = `{_escape_js(notes_md)}`;",
        html,
    )
    html = re.sub(
        r"(const PULSE_DATA = )\{[\s\S]*?\};",
        lambda _: f"const PULSE_DATA = {json.dumps(pulse_data, indent=12, ensure_ascii=False)};",
        html,
    )
    html = re.sub(
        r"(const FEE_DATA = )\{[\s\S]*?\};",
        lambda _: f"const FEE_DATA = {json.dumps(fee_data_m2, ensure_ascii=False)};",
        html,
    )
    html = re.sub(
        r"const ANALYTICS_META = \{[^\n]*\};",
        lambda _: f"const ANALYTICS_META = {json.dumps(analytics_meta, ensure_ascii=False)};",
        html,
    )
    html = re.sub(
        r"const KEYWORDS = \[[\s\S]*?\];",
        lambda _: f"const KEYWORDS = {json.dumps(keywords_m2, ensure_ascii=False)};",
        html,
    )
    html = re.sub(
        r"const CATEGORIES_DATA = \[[\s\S]*?\];",
        lambda _: f"const CATEGORIES_DATA = {json.dumps(categories_data, ensure_ascii=False)};",
        html,
    )
    html = re.sub(
        r"const NEGATIVE_REVIEWS = \[[\s\S]*?\];",
        lambda _: f"const NEGATIVE_REVIEWS = {json.dumps(neg_reviews_m2, ensure_ascii=False)};",
        html,
    )

    # Inject capstone dark-gold theme override so it matches the main app
    _THEME = """<style>
/* Capstone theme override — charcoal + gold */
body { background: #0A0C14 !important; }
.blob-1, .blob-2 { display: none !important; }
.tab-btn.active {
  background: linear-gradient(135deg, #C9A84C, #A8863C) !important;
  color: #0A0C14 !important;
  box-shadow: 0 4px 15px rgba(201,168,76,0.35) !important;
}
.tab-btn:hover:not(.active) { background: rgba(201,168,76,0.08) !important; }
.send-btn {
  background: linear-gradient(135deg, #C9A84C, #A8863C) !important;
  color: #0A0C14 !important;
}
.send-btn:hover { box-shadow: 0 8px 20px rgba(201,168,76,0.4) !important; }
header h1 {
  background: linear-gradient(135deg, #F5F0E8, #C9A84C) !important;
  -webkit-background-clip: text !important;
  -webkit-text-fill-color: transparent !important;
}
.status-pill {
  background: rgba(201,168,76,0.12) !important;
  border-color: rgba(201,168,76,0.40) !important;
  color: #C9A84C !important;
}
.status-dot { background: #C9A84C !important; }
.review-badge { border-color: rgba(201,168,76,0.4) !important; color: #C9A84C !important; }
.check-icon { background: rgba(201,168,76,0.15) !important; border-color: rgba(201,168,76,0.4) !important; color: #C9A84C !important; }
.action-num { background: linear-gradient(135deg, #C9A84C, #A8863C) !important; color: #0A0C14 !important; }
</style>"""
    html = html.replace("</head>", _THEME + "\n</head>")

    DASHBOARD.write_text(html, encoding="utf-8")
    print(f"✅ dashboard.html updated — Week of {today_str}")


if __name__ == "__main__":
    run()
