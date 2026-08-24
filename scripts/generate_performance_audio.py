#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import imageio_ffmpeg

from env_utils import load_env_file
from generate_fish_audio import load_config, synthesize


ROOT = Path(__file__).resolve().parents[1]


def ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(command: list[str]) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def make_silence(path: Path, milliseconds: int) -> None:
    seconds = max(milliseconds, 0) / 1000
    if seconds <= 0:
        return
    run_ffmpeg(
        [
            ffmpeg(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            f"{seconds:.3f}",
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(path),
        ]
    )


def concat_mp3(inputs: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as file:
        list_path = Path(file.name)
        for path in inputs:
            escaped = str(path.resolve()).replace("'", "'\\''")
            file.write(f"file '{escaped}'\n")
    try:
        run_ffmpeg(
            [
                ffmpeg(),
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output_path),
            ]
        )
    finally:
        list_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a paced Fish Audio performance from segment JSON.")
    parser.add_argument("--project", required=True, help="Episode slug under projects/.")
    parser.add_argument("--input", default="performance_voiceover.json", help="Segment JSON relative to the episode folder.")
    parser.add_argument("--output", default="work/audio/performance_voiceover.mp3", help="Output MP3 relative to the episode folder.")
    parser.add_argument("--reference-id", default=None, help="Override Fish Audio reference ID.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output and segment files.")
    args = parser.parse_args()

    load_env_file(ROOT / ".env.local")
    api_key = os.getenv("FISH_API_KEY", "").strip()
    if not api_key:
        print("ERROR: FISH_API_KEY is required in .env.local or environment.")
        return 1

    config = load_config()
    tts = config.get("tts", {})
    project_dir = ROOT / "projects" / args.project
    input_path = project_dir / args.input
    output_path = project_dir / args.output
    segment_dir = output_path.parent / f"{output_path.stem}_segments"

    if output_path.exists() and not args.force:
        print(f"Skipping existing file: {output_path}")
        return 0
    if not input_path.exists():
        print(f"ERROR: input segment file does not exist: {input_path}")
        return 1

    data: dict[str, Any] = json.loads(input_path.read_text(encoding="utf-8-sig"))
    segments = data.get("segments", [])
    if not isinstance(segments, list) or not segments:
        print("ERROR: segment file has no segments.")
        return 1

    segment_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []

    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        speed = float(segment.get("speed", tts.get("fish_speed", 0.92)))
        audio_path = segment_dir / f"{index:02d}_voice.mp3"
        synthesize(
            text=text,
            output_path=audio_path,
            api_key=api_key,
            reference_id=(
                str(args.reference_id).strip()
                if args.reference_id is not None
                else str(tts.get("fish_reference_id", "")).strip()
            ),
            model=str(tts.get("fish_model", "s2-pro")).strip(),
            speed=speed,
            sample_rate=int(tts.get("sample_rate", 44100)),
            mp3_bitrate=int(tts.get("mp3_bitrate", 128)),
        )
        parts.append(audio_path)

        pause_ms = int(segment.get("pause_after_ms", 0))
        if pause_ms > 0:
            silence_path = segment_dir / f"{index:02d}_pause_{pause_ms}ms.mp3"
            make_silence(silence_path, pause_ms)
            parts.append(silence_path)
        print(f"Generated segment {index}: speed={speed:.2f}, pause={pause_ms}ms")

    concat_mp3(parts, output_path)
    print(f"Generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
