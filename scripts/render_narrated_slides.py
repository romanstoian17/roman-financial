#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FPS = 30


def run(command: list[str]) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


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
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def fit_cover(image: Image.Image, width: int, height: int, zoom: float, pan_x: float, pan_y: float) -> Image.Image:
    iw, ih = image.size
    scale = max(width / iw, height / ih) * zoom
    resized = image.resize((int(iw * scale), int(ih * scale)), Image.Resampling.LANCZOS)
    max_x = max(0, resized.width - width)
    max_y = max(0, resized.height - height)
    left = int(max_x * pan_x)
    top = int(max_y * pan_y)
    return resized.crop((left, top, left + width, top + height))


def fit_cover_static(image: Image.Image, width: int, height: int, pan_x: float, pan_y: float) -> Image.Image:
    return fit_cover(image, width, height, 1.0, pan_x, pan_y)


def camera_frame(base: Image.Image, width: int, height: int, local: float, motion: str) -> Image.Image:
    # Render from a slightly oversized static crop, then use subpixel affine transforms.
    # This avoids the integer crop stepping that made tiny zooms look jumpy.
    if motion == "hold":
        return base.copy()
    max_zoom = 1.018
    eased = local * local * (3 - 2 * local)
    if motion == "zoom_out":
        scale = max_zoom - eased * (max_zoom - 1.0)
    else:
        scale = 1.0 + eased * (max_zoom - 1.0)
    cx = width / 2
    cy = height / 2
    a = 1 / scale
    matrix = (a, 0, cx - cx * a, 0, a, cy - cy * a)
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
    font = load_font(34 if width < height else 38, bold=True)
    small = load_font(19)
    draw = ImageDraw.Draw(frame)
    max_text_width = width - 92
    lines = wrap_text(draw, text, font, max_text_width)
    max_lines = 3 if width > height else 4
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    line_height = 43 if width < height else 47
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
        fill=(255, 251, 238, 160),
        stroke_width=2,
        stroke_fill=(9, 18, 26, 110),
    )


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


def scene_audio_path(project_dir: Path, audio_subdir: str, index: int, scene_id: str) -> Path:
    return project_dir / "work" / "audio" / audio_subdir / f"{index:02d}_{scene_id}.mp3"


def render(project: str, orientation: str, version_label: str, image_subdir: str, audio_subdir: str) -> Path:
    project_dir = ROOT / "projects" / project
    plan = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8-sig"))
    scenes: list[dict[str, Any]] = plan["scenes"]
    width, height = (720, 1280) if orientation == "vertical" else (1280, 720)
    suffix = "vertical" if orientation == "vertical" else "landscape"
    output = project_dir / "output" / f"{project}_narrated_{version_label}_{suffix}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    scene_audio_paths: list[Path] = []
    for index, scene in enumerate(scenes, start=1):
        audio_path = scene_audio_path(project_dir, audio_subdir, index, str(scene["id"]))
        if not audio_path.exists():
            raise RuntimeError(
                f"Missing scene audio: {audio_path}. Run scripts/generate_scene_audio.py first."
            )
        scene_audio_paths.append(audio_path)

    with tempfile.TemporaryDirectory(prefix="narrated-slides-", dir=project_dir / "work") as tmp:
        frames_dir = Path(tmp) / "frames"
        frames_dir.mkdir()
        frame_index = 0
        for scene, scene_audio in zip(scenes, scene_audio_paths):
            bg = Image.open(project_dir / "input" / image_subdir / f"{scene['id']}.png").convert("RGB")
            scene_frames = max(1, round(audio_duration(scene_audio) * FPS))
            pan_x, pan_y = pan_for(scene)
            motion = str(scene.get("motion", "zoom_in"))
            base = fit_cover_static(bg, width, height, pan_x, pan_y)
            for i in range(scene_frames):
                local = i / max(1, scene_frames - 1)
                frame = camera_frame(base, width, height, local, motion).convert("RGBA")
                frame.alpha_composite(Image.new("RGBA", frame.size, (9, 18, 26, 18)))
                draw_subtitle(frame, str(scene.get("narration", scene["subtitle"])), width, height)
                frame.convert("RGB").save(frames_dir / f"frame_{frame_index:05d}.jpg", quality=91)
                frame_index += 1

        silent = Path(tmp) / "silent.mp4"
        concat_audio_list = Path(tmp) / "audio.txt"
        concat_audio_list.write_text(
            "".join(f"file '{path.as_posix()}'\n" for path in scene_audio_paths),
            encoding="utf-8",
        )
        joined_audio = Path(tmp) / "joined_audio.mp3"
        run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_audio_list),
                "-c",
                "copy",
                str(joined_audio),
            ]
        )
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
                str(silent),
            ]
        )
        run(
            [
                "ffmpeg",
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
    parser = argparse.ArgumentParser(description="Render a narrator-led slide video without avatar overlay.")
    parser.add_argument("--project", required=True, help="Episode slug under projects/.")
    parser.add_argument("--orientation", choices=("landscape", "vertical"), default="vertical")
    parser.add_argument("--version-label", default="v4", help="Output version label, such as v5.")
    parser.add_argument("--image-subdir", default="images", help="Subfolder under input containing scene images.")
    parser.add_argument("--audio-subdir", default="scenes", help="Subfolder under work/audio containing scene MP3 files.")
    args = parser.parse_args()
    output = render(args.project, args.orientation, args.version_label, args.image_subdir, args.audio_subdir)
    print(f"Rendered: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
