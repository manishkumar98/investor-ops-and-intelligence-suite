"""CLI entry point: python scripts/ingest_corpus.py [--force]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_env
from phase2_corpus_pillar_a.ingest import ingest_corpus, ingest_local_files

if __name__ == "__main__":
    load_env()
    force = "--force" in sys.argv

    # Step 1: URL-based ingest from SOURCE_MANIFEST.md
    result = ingest_corpus(force=force)

    # Step 2: Local pre-scraped files from data/raw/ (M1 Playwright-scraped content)
    local = ingest_local_files()

    print(
        f"\n=== Ingest complete ===\n"
        f"  mf_faq_corpus: {result['mf_faq_count']} chunks  (+{local['mf_faq_added']} from local files)\n"
        f"  fee_corpus:    {result['fee_count']} chunks  (+{local['fee_added']} from local files)\n"
        f"  skipped:       {result['skipped']}"
    )
