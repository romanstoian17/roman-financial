# Roman Financial Agent System

This repository builds repeatable YouTube finance explainers using a recurring animated host, scripted context, generated images, Fish Audio voiceover, video assembly, and publish packaging.

## Repository Layout

- `.agents/` contains role prompts for Codex/subagents.
- `workflow/` contains the operating playbook.
- `scripts/` contains small Python utilities.
- `library/characters/` stores reusable character references and prompt notes.
- `library/audio/` stores reusable audio notes, not secrets.
- `projects/<episode_slug>/` stores each episode workspace.
- `work/` is scratch space and should not be committed.
- `output/` is for final rendered media and should not be committed by default.

## Safety And Finance Rules

This is educational media, not personalized financial advice. Scripts should avoid telling a specific viewer what they must buy, sell, or invest in. Use examples, assumptions, and plain disclaimers. Any tax, legal, or market claims that can change over time need fresh source checks before publication.

Never hardcode API keys, cookies, passwords, or account tokens. Use `.env.local`, local environment variables, or a secrets manager.

## Agent Roles

1. **Planning Producer** decides what to handle first, resolves dependencies, and writes the next execution plan.
2. **Topic Strategist** chooses episode topics and builds topic briefs.
3. **Script Writer** turns a topic brief into a hook, story context, framework, example, and CTA.
4. **Finance Reviewer** checks accuracy, compliance language, and source needs.
5. **Character Director** keeps Roman visually and tonally consistent.
6. **Image Producer** writes scene prompts and tracks generated image assets.
7. **Audio Producer** creates voiceover files with Fish Audio and checks timing.
8. **Video Producer** assembles images, captions, voice, music, and exports the video.
9. **Packaging Agent** prepares title, thumbnail concepts, description, tags, pinned comment, and publish checklist.
10. **Analytics Agent** reviews post-publish performance and recommends the next experiment.

## Default Human Approval Gates

Ask before publishing, spending money, using personal account credentials, changing permanent channel branding, or treating regulated financial advice as personalized guidance.

