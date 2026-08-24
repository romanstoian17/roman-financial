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
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise RuntimeError(result.stderr.strip() or f"Could not read audio duration: {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def scene_audio_path(project_dir: Path, audio_subdir: str, index: int, scene_id: str) -> Path:
    return project_dir / "work" / "audio" / audio_subdir / f"{index:02d}_{scene_id}.mp3"


def render(project: str, image_subdir: str, audio_subdir: str, version_label: str, fps: int, fade: float) -> Path:
    project_dir = ROOT / "projects" / project
    plan = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8-sig"))
    scenes: list[dict[str, Any]] = plan["scenes"]
    output = project_dir / "output" / f"{project}_clean_{version_label}_landscape.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    audio_paths: list[Path] = []
    durations: list[float] = []
    for index, scene in enumerate(scenes, start=1):
        audio_path = scene_audio_path(project_dir, audio_subdir, index, str(scene["id"]))
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise RuntimeError(f"Missing scene audio: {audio_path}")
        audio_paths.append(audio_path)
        durations.append(audio_duration(ffmpeg, audio_path))

    with tempfile.TemporaryDirectory(prefix="clean-preview-", dir=project_dir / "work") as tmp_name:
        tmp = Path(tmp_name)
        clip_paths: list[Path] = []
        for index, scene in enumerate(scenes, start=1):
            image_path = project_dir / "input" / image_subdir / f"{scene['id']}.png"
            clip_path = tmp / f"clip_{index:03d}.mp4"
            # Add fade padding to every clip except the final one so crossfades do not shorten the audio-timed video.
            clip_duration = durations[index - 1] + (fade if index < len(scenes) else 0)
            run(
                [
                    ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-t",
                    f"{clip_duration:.6f}",
                    "-i",
                    str(image_path),
                    "-vf",
                    f"fps={fps},scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,format=yuv420p",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "19",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(fps),
                    str(clip_path),
                ]
            )
            clip_paths.append(clip_path)

        if len(clip_paths) == 1:
            video_no_subs = clip_paths[0]
        else:
            input_args: list[str] = []
            for path in clip_paths:
                input_args.extend(["-i", str(path)])
            chain = "[0:v][1:v]"
            offset = durations[0]
            filter_parts = [f"{chain}xfade=transition=fade:duration={fade}:offset={offset:.6f}[v1]"]
            for idx in range(2, len(clip_paths)):
                offset += durations[idx - 1]
                filter_parts.append(f"[v{idx - 1}][{idx}:v]xfade=transition=fade:duration={fade}:offset={offset:.6f}[v{idx}]")
            video_no_subs = tmp / "video_no_subs.mp4"
            run(
                [
                    ffmpeg,
                    "-y",
                    *input_args,
                    "-filter_complex",
                    ";".join(filter_parts),
                    "-map",
                    f"[v{len(clip_paths) - 1}]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "19",
                    "-pix_fmt",
                    "yuv420p",
                    str(video_no_subs),
                ]
            )

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

        subtitled = tmp / "subtitled.mp4"
        subtitle_filter = (
            f"subtitles='{escape_subtitle_path(srt)}':"
            "force_style='FontName=Segoe UI,FontSize=20,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&HAA000000,BorderStyle=1,Outline=1.4,Shadow=0,MarginV=34'"
        )
        run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(video_no_subs),
                "-vf",
                subtitle_filter,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "19",
                "-pix_fmt",
                "yuv420p",
                str(subtitled),
            ]
        )

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
    parser = argparse.ArgumentParser(description="Render a clean audio preview with static scenes and soft crossfades.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--image-subdir", default="images")
    parser.add_argument("--audio-subdir", required=True)
    parser.add_argument("--version-label", default="v1")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--fade", type=float, default=0.35)
    args = parser.parse_args()
    output = render(args.project, args.image_subdir, args.audio_subdir, args.version_label, args.fps, args.fade)
    print(f"Rendered: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
