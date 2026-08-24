# Narrated Slide Workflow

This is the new primary Roman Financial video direction.

## Direction

Drop the persistent avatar overlay for now.

Instead, each video is built as:

Script -> 5-10 second narration chunks -> one matching generated image per chunk -> voiceover -> animated slides with zoom/pan -> subtitles -> final MP4.

The host exists as a voice and editorial point of view, not as a character pasted onto every frame.

## Why This Is Better

- The visual scene feels complete because every image is generated for the exact narration beat.
- No mismatch between avatar style, lighting, perspective, and background.
- Easier to create richer storytelling scenes.
- Closer to the Financial Historian style: narrator-led finance stories with strong visual metaphors.
- More scalable for Shorts and later long-form videos.

## Standard Episode Shape

For a 45-90 second first-round video:

1. Hook: 5-8 seconds.
2. Context: 6-10 seconds.
3. Mechanism: 6-10 seconds.
4. Example or analogy: 6-10 seconds.
5. Consequence: 6-10 seconds.
6. Practical takeaway: 6-10 seconds.
7. Disclaimer or soft close: 3-6 seconds.

Each beat gets:

- `chunk_id`
- narration text
- target duration
- image prompt
- subtitle text
- motion direction

## Image Rules

Use the Roman Financial primary visual style:

Warm pencil-and-gouache editorial finance explainer on off-white paper, visible pencil linework, soft painted gouache washes, simple readable shapes, deep navy, teal, muted gold, graphite lines, tiny red accent.

For each image:

- Generate the whole scene as one coherent illustration.
- Do not insert the avatar as an overlay.
- Avoid readable AI-generated text.
- Use symbols, icons, boards, charts, documents, buildings, bills, coins, and people only when they support the specific narration chunk.
- Leave room for subtitles near the bottom.
- Keep the image topic-specific, not generic finance wallpaper.

## Motion Rules

Use simple motion:

- Slow zoom in for tension.
- Slow zoom out for summary.
- Gentle pan toward the important object.
- Slight crossfade between chunks.

Avoid busy animation until the still-image system feels strong.

## Subtitle Rules

- Use concise subtitles, not full paragraphs.
- Prefer one sentence per chunk.
- Keep subtitle box clear of the main subject.
- Add exact numeric text in subtitles during editing, not inside generated images.

## Reference Channel

Close format reference:

`https://www.youtube.com/@financial.historian`

Use for pacing and concept shape only. Do not copy titles, scripts, images, voice, or specific packaging.

