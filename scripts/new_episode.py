#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug or "untitled_episode"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Roman Financial episode workspace.")
    parser.add_argument("title", help="Episode title or working topic.")
    parser.add_argument("--slug", default=None, help="Optional explicit episode slug.")
    args = parser.parse_args()

    slug = args.slug or slugify(args.title)
    base = ROOT / "projects" / slug

    for path in [
        base / "input" / "images",
        base / "input" / "music",
        base / "work" / "audio",
        base / "work" / "reviews",
        base / "output",
    ]:
        path.mkdir(parents=True, exist_ok=True)

    brief = base / "brief.md"
    if not brief.exists():
        brief.write_text(
            f"# {args.title}\n\n"
            "## Promise\n\n"
            "Explain the money decision with a simple, practical framework.\n\n"
            "## Target Viewer\n\n"
            "A beginner who wants a clear answer without hype.\n\n"
            "## Notes\n\n"
            "- Keep this educational, not personalized financial advice.\n",
            encoding="utf-8",
        )

    voiceover = base / "voiceover.txt"
    if not voiceover.exists():
        voiceover.write_text(
            "Roman voiceover draft goes here.\n",
            encoding="utf-8",
        )

    scene_plan = base / "scene_plan.json"
    if not scene_plan.exists():
        scene_plan.write_text('{\n  "scenes": []\n}\n', encoding="utf-8")

    print(f"Created episode workspace: {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

