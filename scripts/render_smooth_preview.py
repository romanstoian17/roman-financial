#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import imageio_ffmpeg

from render_zoom_preview import timestamp


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def escape_subtitle_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:")


def audio_duration(ffmpeg: str, path: Path) -> float:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise RuntimeError(result.stderr.strip() or f"Could not read audio duration: {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def motion_filter(scene: dict[str, Any], duration: float, fps: int) -> str:
    motion = str(scene.get("motion", "push_in"))
    d = max(0.001, duration)
    progress = f"(1-cos(min(t/{d:.6f},1)*PI))/2"
    if motion in {"pull_back", "zoom_out"}:
        zoom = f"1.058-0.018*{progress}"
    elif motion in {"pan_left", "pan_right", "tilt_up", "tilt_down", "drift"}:
        zoom = "1.048"
    else:
        zoom = f"1.040+0.018*{progress}"

    x_center = "(in_w-out_w)/2"
    y_center = "(in_h-out_h)/2"
    pan = progress
    if motion == "pan_left":
        x_expr = f"(in_w-out_w)*(0.58-0.16*{pan})"
        y_expr = y_center
    elif motion == "pan_right":
        x_expr = f"(in_w-out_w)*(0.42+0.16*{pan})"
        y_expr = y_center
    elif motion == "tilt_up":
        x_expr = x_center
        y_expr = f"(in_h-out_h)*(0.58-0.16*{pan})"
    elif motion == "tilt_down":
        x_expr = x_center
        y_expr = f"(in_h-out_h)*(0.42+0.16*{pan})"
    else:
        x_expr = x_center
        y_expr = y_center

    return (
        f"fps={fps},"
        f"scale=w='ceil(1280*{zoom}/2)*2':h='ceil(720*{zoom}/2)*2':"
        "force_original_aspect_ratio=increase:eval=frame,"
        f"crop=1280:720:x='{x_expr}':y='{y_expr}',"
        "format=yuv420p"
    )


def scene_audio_path(project_dir: Path, audio_subdir: str, index: int, scene_id: str) -> Path:
    return project_dir / "work" / "audio" / audio_subdir / f"{index:02d}_{scene_id}.mp3"


def render(
    project: str,
    image_subdir: str,
    version_label: str,
    seconds_per_scene: float,
    fps: int,
    audio_subdir: str | None,
) -> Path:
    project_dir = ROOT / "projects" / project
    plan = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8-sig"))
    scenes: list[dict[str, Any]] = plan["scenes"]
    output = project_dir / "output" / f"{project}_smooth_{version_label}_landscape.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    audio_paths: list[Path] = []
    durations: list[float] = []
    if audio_subdir:
        for index, scene in enumerate(scenes, start=1):
            audio_path = scene_audio_path(project_dir, audio_subdir, index, str(scene["id"]))
            if not audio_path.exists() or audio_path.stat().st_size == 0:
                raise RuntimeError(f"Missing scene audio: {audio_path}")
            audio_paths.append(audio_path)
            durations.append(audio_duration(ffmpeg, audio_path))
    else:
        durations = [seconds_per_scene] * len(scenes)

    with tempfile.TemporaryDirectory(prefix="smooth-preview-", dir=project_dir / "work") as tmp_name:
        tmp = Path(tmp_name)
        clip_paths: list[Path] = []
        for index, scene in enumerate(scenes, start=1):
            image_path = project_dir / "input" / image_subdir / f"{scene['id']}.png"
            clip_path = tmp / f"clip_{index:03d}.mp4"
            duration = durations[index - 1]
            run(
                [
                    ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-t",
                    f"{duration:.6f}",
                    "-i",
                    str(image_path),
                    "-vf",
                    motion_filter(scene, duration, fps),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(fps),
                    str(clip_path),
                ]
            )
            clip_paths.append(clip_path)

        concat_list = tmp / "clips.txt"
        concat_list.write_text("".join(f"file '{path.as_posix()}'\n" for path in clip_paths), encoding="utf-8")
        silent = tmp / "silent.mp4"
        run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(silent)])

        srt = tmp / "subtitles.srt"
        lines: list[str] = []
        cursor = 0.0
        for index, scene in enumerate(scenes, start=1):
            start = cursor
            end = cursor + durations[index - 1]
            cursor = end
            text = str(scene.get("narration", scene.get("subtitle", ""))).strip()
            lines.extend([str(index), f"{timestamp(start)} --> {timestamp(end)}", text, ""])
        srt.write_text("\n".join(lines), encoding="utf-8")

        subtitle_filter = (
            f"subtitles='{escape_subtitle_path(srt)}':"
            "force_style='FontName=Segoe UI,FontSize=20,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&HAA000000,BorderStyle=1,Outline=1.4,Shadow=0,MarginV=34'"
        )
        subtitled = tmp / "subtitled.mp4"
        run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(silent),
                "-vf",
                subtitle_filter,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                str(subtitled),
            ]
        )

        if not audio_paths:
            subtitled.replace(output)
            return output

        audio_list = tmp / "audio.txt"
        audio_list.write_text("".join(f"file '{path.as_posix()}'\n" for path in audio_paths), encoding="utf-8")
        joined_audio = tmp / "joined_audio.mp3"
        run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(audio_list), "-c", "copy", str(joined_audio)])
        run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(subtitled),
                "-i",
                str(joined_audio),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(output),
            ]
        )

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a smoother landscape preview from scene images.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--image-subdir", default="images")
    parser.add_argument("--version-label", default="v1")
    parser.add_argument("--seconds-per-scene", type=float, default=6.5)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--audio-subdir", default=None, help="Optional scene-audio folder under work/audio.")
    args = parser.parse_args()
    output = render(args.project, args.image_subdir, args.version_label, args.seconds_per_scene, args.fps, args.audio_subdir)
    print(f"Rendered: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
