# Asset Pipeline Agents

## Character Director

Maintains Roman's visual identity, outfit, expression range, palette, and recurring props. Produces character prompts and approves image consistency.

## Image Producer

Turns scripts into scene prompts. Each prompt should specify Roman, setting, action, mood, aspect ratio, and caption-safe space.

## Audio Producer

Uses Fish Audio through `scripts/generate_fish_audio.py`. Checks for missing MP3s, clipped narration, awkward pacing, and mismatched file names.

## Video Producer

Assembles scenes, captions, voiceover, background music, and exports the final video. Prefer Remotion for repeatable templates; use FFmpeg only for simple assembly or QA.

## Packaging Agent

Creates title options, thumbnail concepts, description, tags, pinned comment, and a final publish checklist.

