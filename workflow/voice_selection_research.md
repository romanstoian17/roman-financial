# Voice Selection Research

Date: 2026-08-24

Goal: choose a Roman Financial voice that feels human, lively, and trustworthy for immigrant-money stories.

## Findings

The best voice for this channel is not simply the deepest or most professional voice. For retention, the voice needs a mix of:

- natural prosody: pitch, rhythm, stress, energy, and pauses;
- conversational warmth;
- clear articulation;
- controlled emotion;
- enough variation to avoid the "same-place monologue" feeling;
- credibility for finance topics without sounding like a bank ad.

Research on TTS naturalness repeatedly points to prosody as the key issue. Modern TTS can sound clean, but often defaults toward an average speaking style unless the workflow adds variation. Fish Audio supports voice references and speed/prosody controls, so the practical workflow should be:

1. Pick a voice with the right base timbre.
2. Write the script with short human phrases.
3. Generate final narration in segments.
4. Vary speed by beat.
5. Add pauses after hooks, turns, caveats, and takeaways.
6. Add audio polish only after the voice and performance pattern are stable.

## Recommended Direction

For Roman Financial, prioritize:

- male voice;
- age impression: young adult to middle-aged;
- accent: neutral North American first, Canadian-friendly if possible;
- emotional shape: warm, curious, mildly skeptical, not salesy;
- energy: medium-lively, not hyper;
- pitch: not too low, because very deep voices can feel less personal for newcomer stories;
- delivery: feels like a person explaining a lesson learned, not announcing a documentary.

## Fish Audio Audition Pack

Generated:

`library/audio/fish_voice_auditions_2026-08-24_lively_human_pack/`

Results copy:

`D:\Ram\projects\projectResults\RomanFinancial\voice_auditions\fish_2026-08-24_lively_human_pack`

Sample text:

> Here is the part nobody tells you when you move to a new country. The first financial goal is not getting rich. It is getting stable. Because once rent, credit, a car payment, and taxes stop surprising you, money finally becomes less emotional. And that is when building wealth starts to feel possible.

## First-Pass Shortlist

Listen first to these:

- `06_warm_conversational_w2w.mp3`
- `08_friendly_confident_male.mp3`
- `10_calm_storyteller_expressive.mp3`
- `11_calm_guy_smooth_confident.mp3`
- `12_gilbert_dynamic_young.mp3`
- `16_adam_friendly_confident.mp3`

For more authoritative alternatives:

- `01_slax_clear_precise.mp3`
- `02_ethan_curious_explainer.mp3`
- `07_authoritative_male_narrator.mp3`
- `17_stickzy_clear_authoritative.mp3`

For high-energy contrast:

- `04_elite_crisp_energetic.mp3`
- `05_alex_fast_social_host.mp3`
- `13_verity_energetic_helper.mp3`
- `14_verity_bright_confident.mp3`
- `15_dynamic_clear_social.mp3`

## Sources

- Fish Audio TTS docs: https://docs.fish.audio/features/text-to-speech
- Fish Audio API reference: https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech
- Apple ML prosody control research: https://machinelearning.apple.com/research/controllable-neural-text-to-speech-synthesis
- Fish Audio S2 technical report: https://arxiv.org/abs/2603.08823
- Voice naturalness discussion: https://www.wellsaid.io/resources/blog/naturalness-primary-driver-synthetic-voice
