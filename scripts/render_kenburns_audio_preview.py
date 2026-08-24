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


def ass_timestamp(seconds: float) -> str:
    centis = round((seconds - int(seconds)) * 100)
    whole = int(seconds)
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    if centis == 100:
        secs += 1
        centis = 0
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def audio_duration(ffmpeg: str, path: Path) -> float:
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise RuntimeError(result.stderr.strip() or f"Could not read audio duration: {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def scene_audio_path(project_dir: Path, audio_subdir: str, index: int, scene_id: str) -> Path:
    return project_dir / "work" / "audio" / audio_subdir / f"{index:02d}_{scene_id}.mp3"


def word_timings(text: str, start: float, duration: float) -> list[tuple[str, float, float]]:
    words = text.split()
    if not words:
        return []
    weights = [max(1.0, len(re.sub(r"[^A-Za-z0-9]", "", word)) * 0.75) for word in words]
    total = sum(weights)
    cursor = start
    timings: list[tuple[str, float, float]] = []
    for word, weight in zip(words, weights):
        word_duration = duration * weight / total
        end = cursor + word_duration
        timings.append((word, cursor, end))
        cursor = end
    if timings:
        word, first_start, _ = timings[-1]
        timings[-1] = (word, first_start, start + duration)
    return timings


def subtitle_pages(words: list[str], max_words: int = 11) -> list[tuple[int, int]]:
    pages: list[tuple[int, int]] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + max_words)
        punctuation_break = None
        for index in range(start + 4, end):
            if words[index].rstrip().endswith((".", "?", "!", ";", ":")):
                punctuation_break = index + 1
        if punctuation_break is not None and punctuation_break > start:
            end = punctuation_break
        pages.append((start, end))
        start = end
    return pages


def paged_subtitle_words(words: list[str], active_index: int, max_words: int = 11) -> list[tuple[str, bool]]:
    for start, end in subtitle_pages(words, max_words):
        if start <= active_index < end:
            return [(words[index], index == active_index) for index in range(start, end)]
    return [(word, index == active_index) for index, word in enumerate(words[:max_words])]


def format_highlight_line(words: list[tuple[str, bool]]) -> str:
    parts: list[str] = []
    for index, (word, active) in enumerate(words):
        color = "&H004AB5E6" if active else "&H00FFFFFF"
        parts.append(f"{{\\c{color}}}{ass_escape(word)}")
        if index == 3 and len(words) > 6:
            parts.append("\\N")
    return " ".join(parts).replace(" \\N ", "\\N")


def write_subtitles(
    path: Path,
    scenes: list[dict[str, Any]],
    durations: list[float],
    mode: str,
) -> None:
    if mode == "static":
        lines: list[str] = []
        cursor = 0.0
        for index, scene in enumerate(scenes, start=1):
            start = cursor
            end = cursor + durations[index - 1]
            cursor = end
            text = str(scene.get("narration", scene.get("subtitle", ""))).strip()
            lines.extend([str(index), f"{timestamp(start)} --> {timestamp(end)}", text, ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Rolling, Segoe UI, 38, &H00FFFFFF, &H00FFFFFF, &HAA000000, &H00000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 2.2, 0, 2, 90, 90, 38, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    cursor = 0.0
    for scene, duration in zip(scenes, durations):
        text = str(scene.get("narration", scene.get("subtitle", ""))).strip()
        timings = word_timings(text, cursor, duration)
        plain_words = [word for word, _, _ in timings]
        for active_index, (_, start, end) in enumerate(timings):
            visible_words = paged_subtitle_words(plain_words, active_index)
            line = format_highlight_line(visible_words)
            events.append(f"Dialogue: 0,{ass_timestamp(start)},{ass_timestamp(end)},Rolling,,0,0,0,,{line}")
        cursor += duration
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def kenburns_filter(scene: dict[str, Any], frames: int, fps: int, internal_width: int, strength: float) -> str:
    motion = str(scene.get("motion", "push_in"))
    n = max(1, frames - 1)
    ease = f"(1-cos(on*PI/{n}))/2"

    push_start = 1.015
    push_delta = 0.08 * strength
    pull_start = 1.105
    pull_delta = 0.08 * strength
    pan_zoom = 1.09 + 0.025 * strength
    pan_amount = 0.28 * strength
    tilt_amount = 0.24 * strength

    if motion in {"pull_back", "zoom_out"}:
        zoom = f"{pull_start:.6f}-{pull_delta:.6f}*{ease}"
    elif motion in {"pan_left", "pan_right", "tilt_up", "tilt_down", "drift"}:
        zoom = f"{pan_zoom:.6f}"
    elif motion == "hold_then_push":
        delayed = f"(1-cos(max(0,(on/{n}-0.35))/0.65*PI))/2"
        zoom = f"{push_start:.6f}+{push_delta:.6f}*{delayed}"
    elif motion == "push_then_hold":
        early = f"(1-cos(min(on/{n}/0.65,1)*PI))/2"
        zoom = f"{push_start:.6f}+{(push_delta * 0.9):.6f}*{early}"
    else:
        zoom = f"{push_start:.6f}+{push_delta:.6f}*{ease}"

    x_center = "iw/2-(iw/zoom/2)"
    y_center = "ih/2-(ih/zoom/2)"
    if motion == "pan_left":
        x = f"(iw-iw/zoom)*({(0.5 + pan_amount / 2):.6f}-{pan_amount:.6f}*{ease})"
        y = y_center
    elif motion == "pan_right":
        x = f"(iw-iw/zoom)*({(0.5 - pan_amount / 2):.6f}+{pan_amount:.6f}*{ease})"
        y = y_center
    elif motion == "tilt_up":
        x = x_center
        y = f"(ih-ih/zoom)*({(0.5 + tilt_amount / 2):.6f}-{tilt_amount:.6f}*{ease})"
    elif motion == "tilt_down":
        x = x_center
        y = f"(ih-ih/zoom)*({(0.5 - tilt_amount / 2):.6f}+{tilt_amount:.6f}*{ease})"
    else:
        x = x_center
        y = y_center

    return (
        f"scale={internal_width}:-2:flags=lanczos,"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s=1280x720:fps={fps},"
        "format=yuv420p"
    )


def render(
    project: str,
    image_subdir: str,
    audio_subdir: str,
    version_label: str,
    fps: int,
    internal_width: int,
    strength: float,
    subtitle_mode: str,
) -> Path:
    project_dir = ROOT / "projects" / project
    plan = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8-sig"))
    scenes: list[dict[str, Any]] = plan["scenes"]
    output = project_dir / "output" / f"{project}_kenburns_{version_label}_landscape.mp4"
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

    with tempfile.TemporaryDirectory(prefix="kenburns-preview-", dir=project_dir / "work") as tmp_name:
        tmp = Path(tmp_name)
        clip_paths: list[Path] = []
        for index, scene in enumerate(scenes, start=1):
            image_path = project_dir / "input" / image_subdir / f"{scene['id']}.png"
            clip_path = tmp / f"clip_{index:03d}.mp4"
            frames = max(2, round(durations[index - 1] * fps))
            run(
                [
                    ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(image_path),
                    "-vf",
                    kenburns_filter(scene, frames, fps, internal_width, strength),
                    "-frames:v",
                    str(frames),
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

        concat_list = tmp / "clips.txt"
        concat_list.write_text("".join(f"file '{path.as_posix()}'\n" for path in clip_paths), encoding="utf-8")
        silent = tmp / "silent.mp4"
        run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(silent)])

        subtitle_path = tmp / ("subtitles.srt" if subtitle_mode == "static" else "subtitles.ass")
        write_subtitles(subtitle_path, scenes, durations, subtitle_mode)

        subtitled = tmp / "subtitled.mp4"
        if subtitle_mode == "static":
            subtitle_filter = (
                f"subtitles='{escape_subtitle_path(subtitle_path)}':"
                "force_style='FontName=Segoe UI,FontSize=20,PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&HAA000000,BorderStyle=1,Outline=1.4,Shadow=0,MarginV=34'"
            )
        else:
            subtitle_filter = f"subtitles='{escape_subtitle_path(subtitle_path)}'"
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
    parser = argparse.ArgumentParser(description="Render audio preview with subtle Ken Burns motion.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--image-subdir", default="images")
    parser.add_argument("--audio-subdir", required=True)
    parser.add_argument("--version-label", default="v1")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--internal-width", type=int, default=5120)
    parser.add_argument("--strength", type=float, default=1.0)
    parser.add_argument("--subtitle-mode", choices=("static", "rolling-highlight"), default="rolling-highlight")
    args = parser.parse_args()
    output = render(
        args.project,
        args.image_subdir,
        args.audio_subdir,
        args.version_label,
        args.fps,
        args.internal_width,
        args.strength,
        args.subtitle_mode,
    )
    print(f"Rendered: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
