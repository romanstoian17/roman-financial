#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FPS = 30


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def run(command: list[str]) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def audio_duration(path: Path) -> float:
    result = subprocess.run(
        [
            ffmpeg_exe(),
            "-hide_banner",
            "-i",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise RuntimeError(result.stderr.strip() or f"Could not read audio duration: {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def cover_oversized(image: Image.Image, width: int, height: int, overscan: float = 1.16) -> Image.Image:
    target_w = int(width * overscan)
    target_h = int(height * overscan)
    iw, ih = image.size
    scale = max(target_w / iw, target_h / ih)
    resized = image.resize((round(iw * scale), round(ih * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def pan_for(scene: dict[str, Any]) -> tuple[float, float]:
    focus = str(scene.get("focus", "center"))
    if focus == "left":
        return 0.35, 0.5
    if focus == "right":
        return 0.65, 0.5
    if focus == "top":
        return 0.5, 0.35
    if focus == "bottom":
        return 0.5, 0.65
    return 0.5, 0.5


def motion_state(scene: dict[str, Any], local: float) -> tuple[float, float, float]:
    motion = str(scene.get("motion", "push_in"))
    base_x, base_y = pan_for(scene)
    e = ease(local)
    scale = 1.012
    x = base_x
    y = base_y

    if motion in {"push_in", "zoom_in"}:
        scale = 1.0 + e * 0.06
    elif motion in {"pull_back", "zoom_out"}:
        scale = 1.06 - e * 0.06
    elif motion == "pan_left":
        scale = 1.035
        x = 0.68 - e * 0.28
    elif motion == "pan_right":
        scale = 1.035
        x = 0.32 + e * 0.28
    elif motion == "tilt_up":
        scale = 1.03
        y = 0.64 - e * 0.24
    elif motion == "tilt_down":
        scale = 1.03
        y = 0.36 + e * 0.24
    elif motion == "hold_then_push":
        delayed = ease(max(0.0, (local - 0.34) / 0.66))
        scale = 1.0 + delayed * 0.055
    elif motion == "push_then_hold":
        early = ease(min(1.0, local / 0.62))
        scale = 1.0 + early * 0.045
    elif motion == "drift":
        scale = 1.025
        x = base_x + math.sin(local * math.tau) * 0.025
        y = base_y + math.sin(local * math.tau * 0.7 + 0.8) * 0.018

    return scale, max(0.0, min(1.0, x)), max(0.0, min(1.0, y))


def camera_frame(base: Image.Image, width: int, height: int, local: float, scene: dict[str, Any]) -> Image.Image:
    scale, pan_x, pan_y = motion_state(scene, local)
    window_w = width / scale
    window_h = height / scale
    max_left = max(0.0, base.width - window_w)
    max_top = max(0.0, base.height - window_h)
    left = max_left * pan_x
    top = max_top * pan_y
    matrix = (window_w / width, 0, left, 0, window_h / height, top)
    return base.transform((width, height), Image.Transform.AFFINE, matrix, Image.Resampling.BICUBIC)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def draw_subtitle(frame: Image.Image, text: str, width: int, height: int) -> None:
    font = load_font(38, bold=True)
    small = load_font(19)
    draw = ImageDraw.Draw(frame)
    max_text_width = width - 92
    lines = wrap_text(draw, text, font, max_text_width)
    max_lines = 3
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    line_height = 47
    y = height - 42 - (line_height * len(lines))

    for line in lines:
        draw.text(
            (width / 2, y),
            line,
            anchor="ma",
            font=font,
            fill=(255, 251, 238, 255),
            stroke_width=4,
            stroke_fill=(9, 18, 26, 220),
        )
        y += line_height

    draw.text(
        (width - 32, 32),
        "Roman Financial",
        anchor="ra",
        font=small,
        fill=(255, 251, 238, 170),
        stroke_width=2,
        stroke_fill=(9, 18, 26, 120),
    )


def draw_polyline(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: tuple[int, int, int, int], width: int) -> None:
    if len(points) >= 2:
        draw.line(points, fill=fill, width=width, joint="curve")


def progressive_points(points: list[tuple[float, float]], progress: float) -> list[tuple[float, float]]:
    if progress <= 0:
        return []
    if progress >= 1:
        return points
    count = max(2, math.ceil(len(points) * progress))
    return points[:count]


def draw_overlay(frame: Image.Image, overlay: str, local: float) -> None:
    width, height = frame.size
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    p = ease(local)
    teal = (28, 125, 132, 190)
    gold = (214, 164, 66, 190)
    red = (178, 61, 55, 175)
    navy = (9, 18, 26, 115)
    ivory = (255, 246, 224, 210)

    if overlay == "question_bubble":
        r = 34 + p * 34
        draw.ellipse((width * 0.49 - r, height * 0.24 - r, width * 0.49 + r, height * 0.24 + r), outline=teal, width=4)
        draw.arc((width * 0.49 - 16, height * 0.24 - 28, width * 0.49 + 16, height * 0.24 + 16), 205, 520, fill=teal, width=5)
        draw.ellipse((width * 0.49 - 3, height * 0.24 + 26, width * 0.49 + 3, height * 0.24 + 32), fill=teal)
    elif overlay == "red_math_warning":
        crack = [(width * 0.47, height * 0.18), (width * 0.50, height * 0.28), (width * 0.48, height * 0.39), (width * 0.53, height * 0.52)]
        draw_polyline(draw, progressive_points(crack, p), red, 5)
    elif overlay == "stack_labels":
        y = height * 0.36
        for idx in range(5):
            x = width * (0.2 + idx * 0.145)
            alpha = int(160 * min(1, max(0, p * 6 - idx)))
            draw.rounded_rectangle((x - 18, y - 18, x + 18, y + 18), radius=8, outline=(28, 125, 132, alpha), width=3)
            if idx:
                draw.line((x - width * 0.145 + 20, y, x - 20, y), fill=(214, 164, 66, alpha), width=3)
    elif overlay == "soft_reveal":
        radius = width * (0.08 + p * 0.42)
        draw.ellipse((width * 0.5 - radius, height * 0.5 - radius, width * 0.5 + radius, height * 0.5 + radius), outline=gold, width=4)
    elif overlay == "growing_bars":
        for idx, frac in enumerate([0.22, 0.36, 0.5, 0.68]):
            h = height * frac * min(1, max(0, p * 5 - idx))
            x = width * (0.62 + idx * 0.045)
            draw.rounded_rectangle((x, height * 0.62 - h, x + 24, height * 0.62), radius=5, fill=teal)
    elif overlay == "debt_clock":
        cx, cy, r = width * 0.73, height * 0.27, 48
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=navy, width=4)
        angle = -90 + p * 270
        end = (cx + math.cos(math.radians(angle)) * (r - 12), cy + math.sin(math.radians(angle)) * (r - 12))
        draw.line((cx, cy, end[0], end[1]), fill=red, width=5)
    elif overlay == "hidden_paths":
        for idx, yoff in enumerate([0.28, 0.38, 0.48]):
            line = [(width * 0.18, height * 0.42), (width * 0.45, height * yoff), (width * 0.78, height * (yoff + 0.08))]
            draw_polyline(draw, progressive_points(line, min(1, p * 1.4 - idx * 0.15)), (28, 125, 132, 130), 4)
    elif overlay == "clock_tick":
        cx, cy, r = width * 0.52, height * 0.29, 54
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=navy, width=4)
        for tick in range(12):
            a = math.radians(tick * 30)
            draw.line((cx + math.cos(a) * (r - 8), cy + math.sin(a) * (r - 8), cx + math.cos(a) * r, cy + math.sin(a) * r), fill=navy, width=2)
        a = math.radians(-90 + p * 360)
        draw.line((cx, cy, cx + math.cos(a) * 34, cy + math.sin(a) * 34), fill=red, width=5)
    elif overlay == "chain_break":
        y = height * 0.31
        for idx in range(7):
            x = width * (0.22 + idx * 0.09)
            alpha = int(185 * min(1, max(0, p * 5 - idx * 0.45)))
            draw.rounded_rectangle((x - 25, y - 12, x + 25, y + 12), radius=11, outline=(9, 18, 26, alpha), width=5)
        if p > 0.72:
            draw.line((width * 0.52, y - 32, width * 0.55, y + 32), fill=red, width=6)
            draw.line((width * 0.55, y - 32, width * 0.52, y + 32), fill=red, width=6)
    elif overlay == "late_profit":
        path = [(width * 0.18, height * 0.52), (width * 0.36, height * 0.43), (width * 0.55, height * 0.46), (width * 0.78, height * 0.31)]
        draw_polyline(draw, progressive_points(path, p), teal, 6)
        if p > 0.85:
            draw.ellipse((width * 0.77 - 10, height * 0.31 - 10, width * 0.77 + 10, height * 0.31 + 10), fill=gold)
    elif overlay == "three_questions":
        for idx in range(3):
            x = width * (0.32 + idx * 0.16)
            y = height * 0.34
            alpha = int(170 * min(1, max(0, p * 4 - idx)))
            draw.rounded_rectangle((x - 42, y - 30, x + 42, y + 30), radius=10, outline=(28, 125, 132, alpha), width=4)
            draw.ellipse((x - 5, y + 14, x + 5, y + 24), fill=(214, 164, 66, alpha))
            draw.arc((x - 18, y - 22, x + 18, y + 16), 205, 520, fill=(214, 164, 66, alpha), width=4)
    elif overlay == "final_clock":
        cx, cy = width * 0.5, height * 0.34
        r = 62 + p * 12
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=gold, width=5)
        draw.arc((cx - r - 24, cy - r - 24, cx + r + 24, cy + r + 24), 10, 350 * p, fill=red, width=4)

    if local < 0.32:
        wash_alpha = int((1 - local / 0.32) * 150)
        draw.rectangle((0, 0, width, height), fill=(ivory[0], ivory[1], ivory[2], wash_alpha))
    frame.alpha_composite(layer)


def scene_audio_path(project_dir: Path, audio_subdir: str, index: int, scene_id: str) -> Path:
    return project_dir / "work" / "audio" / audio_subdir / f"{index:02d}_{scene_id}.mp3"


def render(
    project: str,
    orientation: str,
    version_label: str,
    image_subdir: str,
    audio_subdir: str,
    silent_scene_seconds: float | None = None,
) -> Path:
    project_dir = ROOT / "projects" / project
    plan = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8-sig"))
    scenes: list[dict[str, Any]] = plan["scenes"]
    width, height = (720, 1280) if orientation == "vertical" else (1280, 720)
    suffix = "vertical" if orientation == "vertical" else "landscape"
    output = project_dir / "output" / f"{project}_enhanced_{version_label}_{suffix}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    scene_audio_paths: list[Path] = []
    if silent_scene_seconds is None:
        for index, scene in enumerate(scenes, start=1):
            audio_path = scene_audio_path(project_dir, audio_subdir, index, str(scene["id"]))
            if not audio_path.exists():
                raise RuntimeError(f"Missing scene audio: {audio_path}")
            scene_audio_paths.append(audio_path)

    with tempfile.TemporaryDirectory(prefix="enhanced-slides-", dir=project_dir / "work") as tmp:
        frames_dir = Path(tmp) / "frames"
        frames_dir.mkdir()
        frame_index = 0
        for index, scene in enumerate(scenes):
            image_path = project_dir / "input" / image_subdir / f"{scene['id']}.png"
            bg = Image.open(image_path).convert("RGB")
            base = cover_oversized(bg, width, height)
            duration = silent_scene_seconds if silent_scene_seconds is not None else audio_duration(scene_audio_paths[index])
            scene_frames = max(1, round(duration * FPS))
            for i in range(scene_frames):
                local = i / max(1, scene_frames - 1)
                frame = camera_frame(base, width, height, local, scene).convert("RGBA")
                frame.alpha_composite(Image.new("RGBA", frame.size, (9, 18, 26, 14)))
                draw_overlay(frame, str(scene.get("overlay", "")), local)
                draw_subtitle(frame, str(scene.get("narration", scene.get("subtitle", ""))), width, height)
                frame.convert("RGB").save(frames_dir / f"frame_{frame_index:05d}.jpg", quality=91)
                frame_index += 1

        ffmpeg = ffmpeg_exe()
        if silent_scene_seconds is not None:
            run(
                [
                    ffmpeg,
                    "-y",
                    "-framerate",
                    str(FPS),
                    "-i",
                    str(frames_dir / "frame_%05d.jpg"),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(FPS),
                    str(output),
                ]
            )
            return output

        concat_audio_list = Path(tmp) / "audio.txt"
        concat_audio_list.write_text(
            "".join(f"file '{path.as_posix()}'\n" for path in scene_audio_paths),
            encoding="utf-8",
        )
        joined_audio = Path(tmp) / "joined_audio.mp3"
        silent = Path(tmp) / "silent.mp4"
        run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_audio_list), "-c", "copy", str(joined_audio)])
        run(
            [
                ffmpeg,
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                str(frames_dir / "frame_%05d.jpg"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(FPS),
                str(silent),
            ]
        )
        run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(silent),
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
    parser = argparse.ArgumentParser(description="Render narrated slides with enhanced camera moves and overlays.")
    parser.add_argument("--project", required=True, help="Episode slug under projects/.")
    parser.add_argument("--orientation", choices=("landscape", "vertical"), default="landscape")
    parser.add_argument("--version-label", default="v10")
    parser.add_argument("--image-subdir", default="images")
    parser.add_argument("--audio-subdir", default="scenes")
    parser.add_argument("--silent-scene-seconds", type=float, default=None, help="Render visual-only preview with fixed seconds per scene.")
    args = parser.parse_args()
    output = render(
        args.project,
        args.orientation,
        args.version_label,
        args.image_subdir,
        args.audio_subdir,
        args.silent_scene_seconds,
    )
    print(f"Rendered: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
