#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def concat(inputs: list[Path], output_path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as file:
        list_path = Path(file.name)
        for path in inputs:
            file.write(f"file '{path.resolve().as_posix()}'\n")
    try:
        run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
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
    parser = argparse.ArgumentParser(description="Create per-scene audio files from performance voice/pause segments.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--segment-dir", required=True, help="Folder under work/audio containing NN_voice.mp3 and optional NN_pause_*.mp3.")
    parser.add_argument("--output-subdir", required=True, help="Folder under work/audio for renderer-compatible scene MP3s.")
    args = parser.parse_args()

    project_dir = ROOT / "projects" / args.project
    plan = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8-sig"))
    scenes = plan.get("scenes", [])
    source_dir = project_dir / "work" / "audio" / args.segment_dir
    output_dir = project_dir / "work" / "audio" / args.output_subdir
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, scene in enumerate(scenes, start=1):
        scene_id = str(scene["id"])
        number = f"{index:02d}"
        voice = source_dir / f"{number}_voice.mp3"
        if not voice.exists():
            raise RuntimeError(f"Missing voice segment: {voice}")
        pauses = sorted(source_dir.glob(f"{number}_pause_*.mp3"))
        output = output_dir / f"{number}_{scene_id}.mp3"
        if pauses:
            concat([voice, pauses[0]], output)
        else:
            output.write_bytes(voice.read_bytes())
        print(f"Created: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
