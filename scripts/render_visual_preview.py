#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image

from render_enhanced_slides import FPS, camera_frame, cover_oversized, draw_overlay, draw_subtitle


ROOT = Path(__file__).resolve().parents[1]


def render(project: str, image_subdir: str, version_label: str, seconds_per_scene: float, fps: int) -> Path:
    project_dir = ROOT / "projects" / project
    plan = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8-sig"))
    scenes: list[dict[str, Any]] = plan["scenes"]
    width, height = 1280, 720
    output = project_dir / "output" / f"{project}_visual_preview_{version_label}_landscape.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    frame_count = max(1, round(seconds_per_scene * fps))
    with imageio.get_writer(
        output,
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
        ffmpeg_log_level="error",
        macro_block_size=1,
    ) as writer:
        for scene in scenes:
            image_path = project_dir / "input" / image_subdir / f"{scene['id']}.png"
            bg = Image.open(image_path).convert("RGB")
            base = cover_oversized(bg, width, height)
            for i in range(frame_count):
                local = i / max(1, frame_count - 1)
                frame = camera_frame(base, width, height, local, scene).convert("RGBA")
                draw_overlay(frame, str(scene.get("overlay", "")), local)
                draw_subtitle(frame, str(scene.get("narration", scene.get("subtitle", ""))), width, height)
                writer.append_data(np.asarray(frame.convert("RGB")))

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a fast visual-only landscape preview.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--image-subdir", default="images")
    parser.add_argument("--version-label", default="v1")
    parser.add_argument("--seconds-per-scene", type=float, default=5.0)
    parser.add_argument("--fps", type=int, default=18)
    args = parser.parse_args()
    # Keep imported animation math tied to the main renderer unless the caller requests a draft rate.
    if args.fps <= 0:
        args.fps = FPS
    output = render(args.project, args.image_subdir, args.version_label, args.seconds_per_scene, args.fps)
    print(f"Rendered: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
