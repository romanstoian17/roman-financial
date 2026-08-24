#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FPS = 12


def run(command: list[str]) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(details)


def audio_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return float(result.stdout.strip())


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def fit_cover(image: Image.Image, width: int, height: int, zoom: float, pan_x: float, pan_y: float) -> Image.Image:
    iw, ih = image.size
    scale = max(width / iw, height / ih) * zoom
    nw = int(iw * scale)
    nh = int(ih * scale)
    resized = image.resize((nw, nh), Image.Resampling.LANCZOS)
    max_x = max(0, nw - width)
    max_y = max(0, nh - height)
    left = int(max_x * pan_x)
    top = int(max_y * pan_y)
    return resized.crop((left, top, left + width, top + height))


def draw_caption(frame: Image.Image, text: str, width: int, height: int) -> None:
    draw = ImageDraw.Draw(frame)
    font = load_font(46 if width > height else 38, bold=True)
    small = load_font(20)
    margin = 42
    y = height - 128
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    box_w = min(width - margin * 2, text_w + 70)
    x = (width - box_w) // 2
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((x, y, x + box_w, y + 74), radius=18, fill=(14, 28, 44, 218))
    od.text((x + box_w / 2, y + 35), text, anchor="mm", font=font, fill=(255, 251, 238, 255))
    od.text((width - 42, 34), "Roman Financial", anchor="ra", font=small, fill=(255, 251, 238, 170))
    frame.alpha_composite(overlay)


def build_avatar_layers(avatar: Image.Image, width: int, height: int) -> tuple[Image.Image, Image.Image]:
    target_h = 575 if width > height else 735
    scale = target_h / avatar.height
    target_w = int(avatar.width * scale)
    av = avatar.resize((target_w, target_h), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", av.size, (0, 0, 0, 0))
    alpha = av.getchannel("A").filter(ImageFilter.GaussianBlur(7))
    shadow.putalpha(alpha.point(lambda p: min(95, p // 3)))
    return av, shadow


def composite_avatar(
    frame: Image.Image,
    avatar_layer: Image.Image,
    shadow_layer: Image.Image,
    position: str,
    progress: float,
    width: int,
    height: int,
) -> None:
    target_h = avatar_layer.height
    bob = int(math.sin(progress * math.tau) * 4)
    if width > height:
        x = 790 if position == "right" else 40
        y = height - target_h + 34 + bob
    else:
        x = (width - avatar_layer.width) // 2
        y = height - target_h - 170 + bob
    frame.alpha_composite(shadow_layer, (x + 10, y + 12))
    frame.alpha_composite(avatar_layer, (x, y))


def render(project: str, orientation: str) -> Path:
    project_dir = ROOT / "projects" / project
    plan = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8-sig"))
    scenes: list[dict[str, Any]] = plan["scenes"]
    audio_path = project_dir / "work" / "audio" / "voiceover.mp3"
    avatar_path = ROOT / str(plan.get("avatar_overlay", "library/characters/roman_casual_v1.png"))
    width, height = (720, 1280) if orientation == "vertical" else (1280, 720)
    suffix = "vertical" if orientation == "vertical" else "landscape"
    output = project_dir / "output" / f"pay_off_debt_or_invest_first_v1_{suffix}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    total_audio = audio_duration(audio_path)
    planned = sum(float(scene["duration_seconds"]) for scene in scenes)
    scale = total_audio / planned
    avatar = Image.open(avatar_path).convert("RGBA")
    avatar_layer, shadow_layer = build_avatar_layers(avatar, width, height)

    with tempfile.TemporaryDirectory(prefix="roman-short-", dir=project_dir / "work") as tmp:
        frames_dir = Path(tmp) / "frames"
        frames_dir.mkdir()
        frame_index = 0

        for scene_i, scene in enumerate(scenes):
            image_path = project_dir / "input" / "images" / f"{scene['id']}.png"
            bg = Image.open(image_path).convert("RGB")
            scene_seconds = float(scene["duration_seconds"]) * scale
            scene_frames = max(1, round(scene_seconds * FPS))
            pan_x = 0.42 if scene.get("roman_position") == "right" else 0.58
            pan_y = 0.5

            for i in range(scene_frames):
                local = i / max(1, scene_frames - 1)
                zoom = 1.03 + local * 0.045
                frame = fit_cover(bg, width, height, zoom, pan_x, pan_y).convert("RGBA")
                tint = Image.new("RGBA", frame.size, (10, 22, 33, 22))
                frame.alpha_composite(tint)
                composite_avatar(
                    frame,
                    avatar_layer,
                    shadow_layer,
                    str(scene["roman_position"]),
                    local + scene_i * 0.17,
                    width,
                    height,
                )
                draw_caption(frame, str(scene["caption"]), width, height)
                frame.convert("RGB").save(frames_dir / f"frame_{frame_index:05d}.jpg", quality=92)
                frame_index += 1

        silent_video = Path(tmp) / "silent.mp4"
        run(
            [
                "ffmpeg",
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
                str(silent_video),
            ]
        )
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(silent_video),
                "-i",
                str(audio_path),
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
    parser = argparse.ArgumentParser(description="Render a simple Roman Financial short from scene images.")
    parser.add_argument("--project", required=True, help="Episode slug under projects/.")
    parser.add_argument(
        "--orientation",
        choices=("landscape", "vertical"),
        default="landscape",
        help="Render 16:9 landscape or 9:16 vertical.",
    )
    args = parser.parse_args()
    output = render(args.project, args.orientation)
    print(f"Rendered: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
