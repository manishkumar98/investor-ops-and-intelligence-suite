"""Backup script — run: python scripts/backup_data.py [--dest <path>]

Snapshots:
  - data/chroma/          (ChromaDB vector store)
  - data/*.json           (mcp_state, system_state, mock_calendar)
  - SOURCE_MANIFEST.md
  - .streamlit/config.toml

Backup goes to data/backups/backup_YYYYMMDD_HHMMSS/ by default.
Writes last-backup info to data/system_state.json.
Retains the 5 most recent backups; older ones are pruned automatically.
"""
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "data" / "system_state.json"
BACKUP_ROOT = ROOT / "data" / "backups"
KEEP_LAST_N = 5

ITEMS_TO_BACKUP = [
    "data/chroma",
    "data/mcp_state.json",
    "data/system_state.json",
    "data/mock_calendar.json",
    "SOURCE_MANIFEST.md",
    ".streamlit/config.toml",
]


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


def _dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    if path.is_file():
        return path.stat().st_size / 1_048_576
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1_048_576


def _prune_old_backups(keep: int) -> list[str]:
    """Remove oldest backups beyond the retention limit."""
    existing = sorted(BACKUP_ROOT.glob("backup_*"), key=lambda p: p.name)
    pruned = []
    while len(existing) > keep:
        oldest = existing.pop(0)
        shutil.rmtree(oldest, ignore_errors=True)
        pruned.append(oldest.name)
    return pruned


# ── main ──────────────────────────────────────────────────────────────────────

def run(dest: Path | None = None) -> dict:
    timestamp = datetime.now(timezone.utc)
    tag = timestamp.strftime("%Y%m%d_%H%M%S")
    backup_dir = dest or (BACKUP_ROOT / f"backup_{tag}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    copied, skipped = [], []

    for item_str in ITEMS_TO_BACKUP:
        src = ROOT / item_str
        dst = backup_dir / item_str

        if not src.exists():
            skipped.append(item_str)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        copied.append(item_str)

    total_mb = _dir_size_mb(backup_dir)
    duration = round(time.time() - t0, 2)

    pruned = _prune_old_backups(KEEP_LAST_N)

    record = {
        "timestamp": timestamp.isoformat(),
        "path": str(backup_dir.relative_to(ROOT)),
        "size_mb": round(total_mb, 2),
        "duration_seconds": duration,
        "items_copied": copied,
        "items_skipped": skipped,
        "pruned_backups": pruned,
    }

    state = _read_state()
    state["last_backup"] = record
    _write_state(state)

    return record


def print_report(r: dict) -> None:
    PASS = "\033[32m✔\033[0m"
    SKIP = "\033[33m–\033[0m"
    print(f"\n{'─'*52}")
    print(f"  Backup  —  {r['timestamp'][:19].replace('T', ' ')} UTC")
    print(f"  Destination: {r['path']}")
    print(f"{'─'*52}")
    for item in r["items_copied"]:
        print(f"  {PASS}  {item}")
    for item in r["items_skipped"]:
        print(f"  {SKIP}  {item}  (not found — skipped)")
    if r["pruned_backups"]:
        print(f"\n  Pruned old backups: {', '.join(r['pruned_backups'])}")
    print(f"{'─'*52}")
    print(f"  Total size: {r['size_mb']} MB  |  Time: {r['duration_seconds']}s\n")


if __name__ == "__main__":
    dest = None
    if "--dest" in sys.argv:
        idx = sys.argv.index("--dest")
        if idx + 1 < len(sys.argv):
            dest = Path(sys.argv[idx + 1])

    record = run(dest=dest)
    print_report(record)
