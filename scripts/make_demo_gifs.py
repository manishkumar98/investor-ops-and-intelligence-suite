"""
Extract per-scene GIFs from the demo video.

Usage:
    1. Download the demo from Google Drive into the repo as assets/demo.mp4
       (https://drive.google.com/file/d/1DGWTwK4h0EVvbnfaNS6LueW3tdlug2Rl/view)
    2. Edit the SCENES list below — each entry is (name, start, duration)
       with start/duration in either seconds (int/float) or "MM:SS" / "HH:MM:SS"
       strings.  Re-time after watching the recording so each scene captures
       the relevant flow.
    3. Run:  python scripts/make_demo_gifs.py
       (override the video path with --video PATH if not at assets/demo.mp4)
    4. GIFs land in assets/gifs/<name>.gif and are referenced by README.md.

Requires `ffmpeg` on PATH.  No Python dependencies beyond the stdlib.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# ── Edit these to match your recording ───────────────────────────────────────
# Each tuple: (gif_name, start_time, duration_seconds)
# start_time accepts numbers (seconds) or "MM:SS" / "HH:MM:SS" strings.
SCENES: list[tuple[str, str | float, str | float]] = [
    ("smart_sync_faq",   "00:15",  10),   # Smart-Sync FAQ — per-fund scrape progress
    ("insight_pipeline", "01:00",  12),   # Weekly Pulse generation
    ("voice_agent",      "02:00",  15),   # Voice booking conversation
    ("mcp_workflow",     "03:30",  10),   # Action Centre approve flow
]

# GIF output settings
WIDTH        = 880          # px — keep ≤ 1000 for GitHub README rendering speed
FPS          = 12           # 10–15 looks smooth and keeps file size reasonable
LOOP         = 0            # 0 = infinite
OUT_DIR      = Path(__file__).resolve().parents[1] / "assets" / "gifs"
# First existing path wins.  Add yours to the front if you keep the file
# elsewhere — paths are resolved at runtime in main().
_VIDEO_CANDIDATES = [
    "assets/demo.mp4",
    "assets/demo.mov",
    "DemoVideo_InvestorOps.mov",
    "DemoVideo_InvestorOps.mp4",
]
DEFAULT_VIDEO = Path(__file__).resolve().parents[1] / "assets" / "demo.mp4"


def _to_seconds(v: str | float) -> float:
    """Accept '01:23', '1:23:45' or numeric seconds; return float seconds."""
    if isinstance(v, (int, float)):
        return float(v)
    parts = [float(p) for p in v.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


def extract_gif(video: Path, out: Path, start: float, duration: float) -> None:
    """ffmpeg two-pass: build a colour palette then encode the GIF."""
    out.parent.mkdir(parents=True, exist_ok=True)
    palette = out.with_suffix(".palette.png")
    vf_filter = f"fps={FPS},scale={WIDTH}:-1:flags=lanczos"

    # Pass 1: extract optimal palette
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{start}", "-t", f"{duration}", "-i", str(video),
            "-vf", f"{vf_filter},palettegen=stats_mode=diff",
            str(palette),
        ],
        check=True,
    )
    # Pass 2: encode GIF using the palette
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{start}", "-t", f"{duration}", "-i", str(video),
            "-i", str(palette),
            "-lavfi", f"{vf_filter} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5",
            "-loop", str(LOOP),
            str(out),
        ],
        check=True,
    )
    palette.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", default=None,
                    help="path to the demo video (auto-detected if omitted)")
    ap.add_argument("--scene", help="only extract this scene name")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("✗ ffmpeg is not installed. brew install ffmpeg / "
                 "apt-get install ffmpeg / choco install ffmpeg")

    repo_root = Path(__file__).resolve().parents[1]
    video = Path(args.video) if args.video else None
    if not video or not video.exists():
        for cand in _VIDEO_CANDIDATES:
            p = repo_root / cand
            if p.exists():
                video = p
                break
    if not video or not video.exists():
        sys.exit(
            f"✗ demo video not found.  Tried:\n"
            + "\n".join(f"    - {c}" for c in _VIDEO_CANDIDATES)
            + "\n  Download from "
            "https://drive.google.com/file/d/1DGWTwK4h0EVvbnfaNS6LueW3tdlug2Rl/view "
            "or pass --video PATH"
        )
    print(f"📹 using video: {video.relative_to(repo_root)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = [s for s in SCENES if not args.scene or s[0] == args.scene]
    if not targets:
        sys.exit(f"✗ no scene named {args.scene!r} in SCENES")

    for name, start, duration in targets:
        out = OUT_DIR / f"{name}.gif"
        s = _to_seconds(start)
        d = _to_seconds(duration)
        print(f"→ {name}: {s:.1f}s + {d:.1f}s  →  {out.relative_to(OUT_DIR.parents[1])}")
        try:
            extract_gif(video, out, s, d)
            print(f"  ✓ {out.stat().st_size // 1024} KB")
        except subprocess.CalledProcessError as exc:
            print(f"  ✗ ffmpeg failed: {exc}")


if __name__ == "__main__":
    main()
