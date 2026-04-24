"""Health monitor — run: python scripts/health_monitor.py

Checks corpus freshness, ChromaDB integrity, API key presence,
required data files, and package imports. Writes results to
data/system_state.json under the "last_health_check" key.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE_FILE = ROOT / "data" / "system_state.json"

REQUIRED_DATA_FILES = [
    "data/mock_calendar.json",
    "SOURCE_MANIFEST.md",
]

REQUIRED_PACKAGES = [
    "anthropic",
    "chromadb",
    "streamlit",
    "sentence_transformers",
]

# Warn if corpus is older than this many hours
STALE_AFTER_HOURS = 48


# ── helpers ───────────────────────────────────────────────────────────────────

def _read_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _check(name: str, fn) -> dict:
    """Run a single check, return {name, status, detail}."""
    try:
        detail = fn()
        return {"name": name, "status": "ok", "detail": detail}
    except Exception as exc:
        return {"name": name, "status": "fail", "detail": str(exc)}


# ── individual checks ─────────────────────────────────────────────────────────

def check_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    masked = key[:8] + "..." + key[-4:]
    return f"present ({masked})"


def check_chromadb_collections() -> str:
    from phase2_corpus_pillar_a.ingest import get_collection
    faq = get_collection("mf_faq_corpus").count()
    fee = get_collection("fee_corpus").count()
    if faq == 0 or fee == 0:
        raise RuntimeError(f"Empty collection — faq={faq}, fee={fee}")
    return f"mf_faq_corpus={faq} chunks, fee_corpus={fee} chunks"


def check_corpus_freshness() -> str:
    state = _read_state()
    last = state.get("last_ingest", {}).get("timestamp")
    if not last:
        raise RuntimeError("No ingest timestamp recorded — run ingest_corpus.py")
    dt = datetime.fromisoformat(last)
    age_h = (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).total_seconds() / 3600
    if age_h > STALE_AFTER_HOURS:
        raise RuntimeError(f"Corpus is {age_h:.1f}h old (threshold {STALE_AFTER_HOURS}h) — re-ingest recommended")
    return f"Last ingest {age_h:.1f}h ago ({last})"


def check_data_files() -> str:
    missing = [f for f in REQUIRED_DATA_FILES if not (ROOT / f).exists()]
    if missing:
        raise RuntimeError(f"Missing: {', '.join(missing)}")
    return "all present"


def check_packages() -> str:
    import importlib
    failed = []
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            failed.append(pkg)
    if failed:
        raise RuntimeError(f"Missing packages: {', '.join(failed)}")
    return "all importable"


def check_source_manifest() -> str:
    manifest = ROOT / "SOURCE_MANIFEST.md"
    urls = [l for l in manifest.read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    if len(urls) < 5:
        raise RuntimeError(f"Only {len(urls)} URLs in SOURCE_MANIFEST.md — seems too few")
    return f"{len(urls)} URL entries"


def check_chroma_dir() -> str:
    chroma = ROOT / "data" / "chroma"
    if not chroma.exists():
        raise RuntimeError("data/chroma/ not found")
    size_mb = sum(f.stat().st_size for f in chroma.rglob("*") if f.is_file()) / 1_048_576
    return f"data/chroma/ exists, {size_mb:.2f} MB"


# ── main ──────────────────────────────────────────────────────────────────────

CHECKS = [
    ("API Key",              check_api_key),
    ("ChromaDB collections", check_chromadb_collections),
    ("Corpus freshness",     check_corpus_freshness),
    ("Data files",           check_data_files),
    ("Python packages",      check_packages),
    ("Source manifest",      check_source_manifest),
    ("Chroma directory",     check_chroma_dir),
]

PASS = "\033[32m✔\033[0m"
FAIL = "\033[31m✘\033[0m"
WARN = "\033[33m⚠\033[0m"


def run() -> dict:
    from config import load_env
    load_env()

    t0 = time.time()
    results = []
    for name, fn in CHECKS:
        r = _check(name, fn)
        results.append(r)

    overall = "healthy" if all(r["status"] == "ok" for r in results) else "degraded"
    duration = round(time.time() - t0, 2)
    timestamp = datetime.now(timezone.utc).isoformat()

    report = {
        "timestamp": timestamp,
        "status": overall,
        "duration_seconds": duration,
        "checks": results,
    }

    # Persist to system_state.json
    state = _read_state()
    state["last_health_check"] = report
    _write_state(state)

    return report


def print_report(report: dict) -> None:
    print(f"\n{'─'*52}")
    print(f"  Health Check  —  {report['timestamp'][:19].replace('T', ' ')} UTC")
    print(f"{'─'*52}")
    for r in report["checks"]:
        icon = PASS if r["status"] == "ok" else FAIL
        print(f"  {icon}  {r['name']:<28}  {r['detail']}")
    print(f"{'─'*52}")
    status_color = "\033[32m" if report["status"] == "healthy" else "\033[31m"
    print(f"  Overall: {status_color}{report['status'].upper()}\033[0m  "
          f"({report['duration_seconds']}s)\n")


if __name__ == "__main__":
    report = run()
    print_report(report)
    sys.exit(0 if report["status"] == "healthy" else 1)
