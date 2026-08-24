#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from env_utils import load_env_file
from generate_fish_audio import load_config, synthesize


ROOT = Path(__file__).resolve().parents[1]


def synthesize_edge(
    text_path: Path,
    output_path: Path,
    voice: str,
    rate: str,
    pitch: str,
    volume: str,
) -> None:
    command = [
        sys.executable,
        "-m",
        "edge_tts",
        "--voice",
        voice,
        f"--rate={rate}",
        f"--pitch={pitch}",
        f"--volume={volume}",
        "--file",
        str(text_path),
        "--write-media",
        str(output_path),
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"edge-tts did not produce audio: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one Fish Audio MP3 per scene narration.")
    parser.add_argument("--project", required=True, help="Episode slug under projects/.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing scene audio files.")
    parser.add_argument("--audio-subdir", default="scenes", help="Subfolder under work/audio for generated MP3 files.")
    parser.add_argument("--engine", choices=("edge", "fish"), default=None, help="Override TTS engine.")
    parser.add_argument("--voice", default=None, help="Override Edge voice name.")
    parser.add_argument("--edge-rate", default=None, help="Override Edge rate, such as +4%%.")
    parser.add_argument("--edge-pitch", default=None, help="Override Edge pitch, such as +2Hz.")
    parser.add_argument("--edge-volume", default=None, help="Override Edge volume, such as +0%%.")
    parser.add_argument("--reference-id", default=None, help="Override Fish Audio reference ID. Use an empty string for the default voice.")
    parser.add_argument("--speed", type=float, default=None, help="Override Fish Audio speech speed.")
    args = parser.parse_args()

    load_env_file(ROOT / ".env.local")

    project_dir = ROOT / "projects" / args.project
    plan_path = project_dir / "scene_plan.json"
    if not plan_path.exists():
        print(f"ERROR: scene plan does not exist: {plan_path}")
        return 1

    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    scenes = plan.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        print("ERROR: scene_plan.json has no scenes.")
        return 1

    config = load_config()
    tts = config.get("tts", {})
    engine = str(args.engine or tts.get("engine", "fish")).strip().lower()
    if engine not in {"edge", "fish"}:
        print(f"ERROR: unsupported TTS engine: {engine}")
        return 1
    api_key = os.getenv("FISH_API_KEY", "").strip()
    if engine == "fish" and not api_key:
        print("ERROR: FISH_API_KEY is required in .env.local or environment.")
        return 1

    audio_dir = project_dir / "work" / "audio" / args.audio_subdir
    text_dir = project_dir / "work" / "audio" / f"{args.audio_subdir}_text"
    audio_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("id", f"scene_{index:02d}"))
        text = str(scene.get("narration", "")).strip()
        if not text:
            print(f"Skipping {scene_id}: no narration")
            continue

        text_path = text_dir / f"{index:02d}_{scene_id}.txt"
        output_path = audio_dir / f"{index:02d}_{scene_id}.mp3"
        text_path.write_text(text + "\n", encoding="utf-8")
        if output_path.exists() and not args.force:
            print(f"Skipping existing: {output_path.name}")
            continue

        if engine == "edge":
            synthesize_edge(
                text_path=text_path,
                output_path=output_path,
                voice=str(args.voice or tts.get("voice", "en-CA-LiamNeural")).strip(),
                rate=str(args.edge_rate or tts.get("edge_rate", "+4%")).strip(),
                pitch=str(args.edge_pitch or tts.get("edge_pitch", "+2Hz")).strip(),
                volume=str(args.edge_volume or tts.get("edge_volume", "+0%")).strip(),
            )
        else:
            synthesize(
                text=text,
                output_path=output_path,
                api_key=api_key,
                reference_id=(
                    str(args.reference_id).strip()
                    if args.reference_id is not None
                    else str(tts.get("fish_reference_id", "")).strip()
                ),
                model=str(tts.get("fish_model", "s2-pro")).strip(),
                speed=float(args.speed if args.speed is not None else tts.get("fish_speed", 0.92)),
                sample_rate=int(tts.get("sample_rate", 44100)),
                mp3_bitrate=int(tts.get("mp3_bitrate", 128)),
            )
        print(f"Generated: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
