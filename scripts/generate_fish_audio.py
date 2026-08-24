#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from env_utils import load_env_file


ROOT = Path(__file__).resolve().parents[1]
FISH_TTS_URL = "https://api.fish.audio/v1/tts"


def load_config() -> dict[str, Any]:
    return json.loads((ROOT / "pipeline_config.json").read_text(encoding="utf-8-sig"))


def synthesize(
    text: str,
    output_path: Path,
    api_key: str,
    reference_id: str,
    model: str,
    speed: float,
    sample_rate: int,
    mp3_bitrate: int,
) -> None:
    payload: dict[str, Any] = {
        "text": text,
        "temperature": 0.7,
        "top_p": 0.7,
        "prosody": {
            "speed": speed,
            "volume": 0,
            "normalize_loudness": True,
        },
        "chunk_length": 300,
        "normalize": True,
        "format": "mp3",
        "sample_rate": sample_rate,
        "mp3_bitrate": mp3_bitrate,
        "latency": "normal",
        "max_new_tokens": 1024,
        "repetition_penalty": 1.2,
        "min_chunk_length": 50,
        "condition_on_previous_chunks": True,
        "early_stop_threshold": 1,
    }
    if reference_id:
        payload["reference_id"] = reference_id

    request = urllib.request.Request(
        FISH_TTS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "model": model,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            output_path.write_bytes(response.read())
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Fish Audio HTTP {error.code}: {details}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Fish Audio request failed: {error}") from error

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Fish Audio did not produce audio: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Roman Financial voiceover with Fish Audio.")
    parser.add_argument("--project", required=True, help="Episode slug under projects/.")
    parser.add_argument("--input", default="voiceover.txt", help="Input text file relative to the episode folder.")
    parser.add_argument("--output", default="work/audio/voiceover.mp3", help="Output MP3 relative to the episode folder.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
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

    if not project_dir.exists():
        print(f"ERROR: project does not exist: {project_dir}")
        return 1
    if not input_path.exists():
        print(f"ERROR: input text file does not exist: {input_path}")
        return 1
    if output_path.exists() and not args.force:
        print(f"Skipping existing file: {output_path}")
        return 0

    text = input_path.read_text(encoding="utf-8").strip()
    if not text:
        print(f"ERROR: input text file is empty: {input_path}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    synthesize(
        text=text,
        output_path=output_path,
        api_key=api_key,
        reference_id=str(tts.get("fish_reference_id", "")).strip(),
        model=str(tts.get("fish_model", "s2-pro")).strip(),
        speed=float(tts.get("fish_speed", 0.92)),
        sample_rate=int(tts.get("sample_rate", 44100)),
        mp3_bitrate=int(tts.get("mp3_bitrate", 128)),
    )
    print(f"Generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

