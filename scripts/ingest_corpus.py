"""CLI entry point: python scripts/ingest_corpus.py [--force]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_env
from pillar_a.ingest import ingest_corpus

if __name__ == "__main__":
    load_env()
    force = "--force" in sys.argv
    result = ingest_corpus(force=force)
    print(
        f"\n=== Ingest complete ===\n"
        f"  mf_faq_corpus: {result['mf_faq_count']} chunks\n"
        f"  fee_corpus:    {result['fee_count']} chunks\n"
        f"  skipped:       {result['skipped']}"
    )
