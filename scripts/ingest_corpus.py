"""CLI entry point: python scripts/ingest_corpus.py [--force]

Writes last-ingest metadata to data/system_state.json after every run.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_env
from phase2_corpus_pillar_a.ingest import ingest_corpus, ingest_local_files

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "system_state.json"


def _read_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _write_last_ingest(result: dict, local: dict, force: bool, duration: float) -> None:
    state = _read_state()
    state["last_ingest"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "force": force,
        "duration_seconds": round(duration, 2),
        "mf_faq_count": result["mf_faq_count"] + local["mf_faq_added"],
        "fee_count": result["fee_count"] + local["fee_added"],
        "url_skipped": result["skipped"],
        "local_files_added": local["mf_faq_added"] + local["fee_added"],
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


if __name__ == "__main__":
    load_env()
    force = "--force" in sys.argv

    t0 = time.time()

    # Step 1: URL-based ingest from SOURCE_MANIFEST.md
    result = ingest_corpus(force=force)

    # Step 2: Local pre-scraped files from data/raw/ (M1 Playwright-scraped content)
    local = ingest_local_files()

    duration = time.time() - t0
    _write_last_ingest(result, local, force, duration)

    print(
        f"\n=== Ingest complete ===\n"
        f"  mf_faq_corpus: {result['mf_faq_count']} chunks  (+{local['mf_faq_added']} from local files)\n"
        f"  fee_corpus:    {result['fee_count']} chunks  (+{local['fee_added']} from local files)\n"
        f"  skipped:       {result['skipped']}\n"
        f"  duration:      {duration:.1f}s\n"
        f"  recorded to:   data/system_state.json"
    )
