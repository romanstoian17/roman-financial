#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import imageio_ffmpeg


ROOT = Path(__file__).resolve().parents[1]


def timestamp(seconds: float) -> str:
    millis = round((seconds - int(seconds)) * 1000)
    whole = int(seconds)
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def escape_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:")


def render(project: str, image_subdir: str, version_label: str, seconds_per_scene: float, fps: int) -> Path:
    project_dir = ROOT / "projects" / project
    plan = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8-sig"))
    scenes: list[dict[str, Any]] = plan["scenes"]
    output = project_dir / "output" / f"{project}_zoom_preview_{version_label}_landscape.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="zoom-preview-", dir=project_dir / "work") as tmp_name:
        tmp = Path(tmp_name)
        for index, scene in enumerate(scenes, start=1):
            src = project_dir / "input" / image_subdir / f"{scene['id']}.png"
            shutil.copyfile(src, tmp / f"scene_{index:03d}.png")

        srt = tmp / "subtitles.srt"
        lines: list[str] = []
        for index, scene in enumerate(scenes, start=1):
            start = (index - 1) * seconds_per_scene
            end = index * seconds_per_scene
            text = str(scene.get("narration", scene.get("subtitle", ""))).strip()
            lines.extend([str(index), f"{timestamp(start)} --> {timestamp(end)}", text, ""])
        srt.write_text("\n".join(lines), encoding="utf-8")

        frames_per_scene = max(1, round(seconds_per_scene * fps))
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        vf = (
            "scale=1400:-2,"
            "zoompan=z='min(zoom+0.00075,1.055)':"
            f"d={frames_per_scene}:s=1280x720:fps={fps}:"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
            f"subtitles='{escape_filter_path(srt)}':"
            "force_style='FontName=Segoe UI,FontSize=20,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H99000000,BorderStyle=1,Outline=1.5,Shadow=0,MarginV=34'"
        )
        command = [
            ffmpeg,
            "-y",
            "-framerate",
            f"1/{seconds_per_scene}",
            "-i",
            str(tmp / "scene_%03d.png"),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            str(output),
        ]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a fast FFmpeg zoompan visual preview.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--image-subdir", default="images")
    parser.add_argument("--version-label", default="v1")
    parser.add_argument("--seconds-per-scene", type=float, default=6.0)
    parser.add_argument("--fps", type=int, default=24)
    args = parser.parse_args()
    output = render(args.project, args.image_subdir, args.version_label, args.seconds_per_scene, args.fps)
    print(f"Rendered: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
