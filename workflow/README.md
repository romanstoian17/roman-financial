# Roman Financial Workflow

## Goal

Build a repeatable pipeline for animated YouTube finance explainers:

Topic -> context -> script -> finance review -> scene prompts -> images -> Fish Audio voiceover -> video render -> packaging -> publish approval.

## First Milestone

Produce one 75-90 second test video without publishing it.

Recommended first topic: **Pay Off Debt or Invest First?**

Why: it is evergreen, relatable, easy to explain with numbers, and establishes Roman as practical instead of hype-driven.

## Episode Workspace

Each episode lives under:

`projects/<episode_slug>/`

Expected files:

- `brief.md`
- `script.md`
- `scene_plan.json`
- `voiceover.txt`
- `input/images/`
- `work/audio/`
- `work/reviews/`
- `output/`
- `publish_package.md`

## Production Steps

1. Create an episode workspace:
   `python scripts/new_episode.py "Pay Off Debt or Invest First"`

2. Write or generate `brief.md`.

3. Write `script.md` and `voiceover.txt`.

4. Run script story-quality review and finance review before generating media:
   `python scripts/review_script_quality.py --project pay_off_debt_or_invest_first`

5. Generate scene prompts in `scene_plan.json`.

6. Generate or place images in `input/images/`.

7. Generate voiceover:
   `python scripts/generate_fish_audio.py --project pay_off_debt_or_invest_first`

8. Assemble video with the selected render path.

9. Create `publish_package.md`.

10. Ask for final approval before upload.

## Fish Audio

Fish Audio uses:

- API key from `.env.local` or the `FISH_API_KEY` environment variable.
- Voice/reference settings from `pipeline_config.json`.

Do not commit `.env.local`.
