#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


GENERIC_AI_PHRASES = [
    "but here's the thing",
    "here's where things get interesting",
    "little did i know",
    "what happened next changed everything",
    "it wasn't just",
    "and that's when everything changed",
    "fast forward to",
    "let that sink in",
]

MECHANICAL_TRANSITIONS = [
    "then",
    "next",
    "after that",
    "afterwards",
    "eventually",
    "finally",
]

CHRONOLOGY_OPENERS = [
    "in 20",
    "i was born",
    "first",
    "then",
    "after that",
    "a few years later",
    "fast forward",
]

TENSION_WORDS = [
    "impossible",
    "problem",
    "difficult",
    "hard",
    "stuck",
    "trap",
    "risk",
    "pressure",
    "surprise",
    "but",
    "however",
    "instead",
    "not always",
    "catch",
    "wrong",
]

PERSONAL_STORY_WORDS = [
    "i ",
    "we ",
    "my ",
    "our ",
    "wife",
    "kids",
    "family",
    "car",
    "rent",
    "home",
    "house",
    "canada",
    "ukraine",
]

HUMOR_SIGNALS = [
    "apparently",
    "politely",
    "as if",
    "pretend",
    "healthy hobbies",
    "strangers on the internet",
    "by tuesday",
]

FINANCE_RISK_PHRASES = [
    "guaranteed",
    "risk free",
    "perfect investment",
    "can't lose",
    "will definitely",
]

ADVICE_PATTERNS = [
    "you should buy",
    "you must buy",
    "you should sell",
    "you must sell",
]


@dataclass(frozen=True)
class Finding:
    label: str
    status: str
    detail: str


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text)


def paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]


def sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def count_phrase(text: str, phrase: str) -> int:
    return len(re.findall(rf"\b{re.escape(phrase)}\b", text.lower()))


def count_any(text: str, phrases: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(phrase) for phrase in phrases)


def sentence_contains_safe_negation(sentence: str) -> bool:
    lower = sentence.lower()
    return any(
        marker in lower
        for marker in [
            "not a video about",
            "not telling you",
            "not saying you should",
            "does not mean you should",
            "doesn't mean you should",
            "whether you should",
            "this is education",
            "not personal financial advice",
        ]
    )


def first_words(text: str, count: int) -> str:
    all_words = words(text)
    return " ".join(all_words[:count])


def score(status: str) -> int:
    return {"pass": 2, "watch": 1, "fail": 0}[status]


def assess_hook(text: str) -> Finding:
    opener = first_words(text, 90).lower()
    starts_with_chronology = any(opener.startswith(item) for item in CHRONOLOGY_OPENERS)
    has_question = "?" in opener
    has_tension = count_any(opener, TENSION_WORDS) > 0
    has_personal_specific = count_any(opener, PERSONAL_STORY_WORDS) >= 2
    has_number_or_contrast = bool(re.search(r"\b\d+|thousand|million|zero|less than|more than|not\b", opener))

    signals = sum([has_question, has_tension, has_personal_specific, has_number_or_contrast])
    if starts_with_chronology and signals < 3:
        return Finding(
            "Hook",
            "fail",
            "Opening leans chronological before creating enough tension, curiosity, or contradiction.",
        )
    if signals >= 3:
        return Finding("Hook", "pass", "Opening contains enough curiosity/tension/specificity to earn attention.")
    if signals == 2:
        return Finding("Hook", "watch", "Opening has some story signals, but could create a sharper reason to stay.")
    return Finding("Hook", "fail", "Opening feels generic or informational.")


def assess_story(text: str) -> Finding:
    lower = text.lower()
    tension = count_any(lower, TENSION_WORDS)
    personal = count_any(lower, PERSONAL_STORY_WORDS)
    questions = text.count("?")
    callbacks = sum(lower.count(word) for word in ["options", "question", "decision", "same", "again"])

    if tension >= 8 and personal >= 12 and (questions >= 2 or callbacks >= 6):
        return Finding("Story", "pass", "Draft has conflict, personal stakes, and recurring story threads.")
    if tension >= 4 and personal >= 6:
        return Finding("Story", "watch", "Draft has story material, but may still need stronger reversals or payoff.")
    return Finding("Story", "fail", "Draft may be explaining facts more than shaping a story.")


def assess_pacing(text: str) -> Finding:
    paras = paragraphs(text)
    if not paras:
        return Finding("Pacing", "fail", "No paragraph breaks found.")

    word_counts = [len(words(para)) for para in paras]
    tiny = sum(1 for count in word_counts if count <= 3)
    long = sum(1 for count in word_counts if count >= 85)
    average_sentence = len(words(text)) / max(len(sentences(text)), 1)

    if tiny > 8:
        return Finding("Pacing", "watch", f"Many tiny beats found ({tiny}); combine any that would create <4s scenes.")
    if long > 3:
        return Finding("Pacing", "watch", f"Several dense paragraphs found ({long}); spoken delivery may feel heavy.")
    if average_sentence > 22:
        return Finding("Pacing", "watch", f"Average sentence length is {average_sentence:.1f} words; tighten for voice.")
    return Finding("Pacing", "pass", "Paragraph and sentence lengths look suitable for spoken narration.")


def assess_ai_language(text: str) -> Finding:
    lower = text.lower()
    generic_hits = {phrase: lower.count(phrase) for phrase in GENERIC_AI_PHRASES if lower.count(phrase)}
    mechanical = sum(count_phrase(lower, phrase) for phrase in MECHANICAL_TRANSITIONS)

    if generic_hits:
        phrases = ", ".join(f"{phrase} ({count})" for phrase, count in generic_hits.items())
        return Finding("AI-language", "fail", f"Generic formula phrases found: {phrases}.")
    if mechanical > 12:
        return Finding("AI-language", "watch", f"Mechanical transition count is high ({mechanical}).")
    return Finding("AI-language", "pass", "No major generic AI-writing phrases detected.")


def assess_voice(text: str) -> Finding:
    lower = text.lower()
    contractions = len(re.findall(r"\b\w+'(?:t|re|s|m|ll|ve|d)\b", lower))
    humor = count_any(lower, HUMOR_SIGNALS)
    direct_viewer = sum(lower.count(item) for item in ["you ", "your ", "let's ", "imagine "])

    if contractions >= 3 and (humor >= 1 or direct_viewer >= 5):
        return Finding("Voice", "pass", "Draft has conversational markers and some personality.")
    if contractions >= 1 or humor >= 1 or direct_viewer >= 3:
        return Finding("Voice", "watch", "Voice is partly conversational, but may need more natural spoken texture.")
    return Finding("Voice", "fail", "Voice may sound too formal or essay-like.")


def assess_finance_integrity(text: str) -> Finding:
    lower = text.lower()
    hits = {phrase: lower.count(phrase) for phrase in FINANCE_RISK_PHRASES if lower.count(phrase)}
    advice_hits: dict[str, int] = {}
    for sentence in sentences(text):
        sentence_lower = sentence.lower()
        if sentence_contains_safe_negation(sentence_lower):
            continue
        for pattern in ADVICE_PATTERNS:
            if pattern in sentence_lower:
                advice_hits[pattern] = advice_hits.get(pattern, 0) + sentence_lower.count(pattern)
    disclaimer = "not personal financial advice" in lower or "education" in lower or "educational" in lower

    risky_hits = {phrase: count for phrase, count in hits.items() if phrase not in {"risk free"}}
    risky_hits.update(advice_hits)
    if risky_hits:
        phrases = ", ".join(f"{phrase} ({count})" for phrase, count in risky_hits.items())
        return Finding("Finance integrity", "fail", f"Potential advice/overcertainty phrase found: {phrases}.")
    if hits.get("risk free") and "does not mean it is risk free" not in lower:
        return Finding("Finance integrity", "fail", "Risk-free wording appears without a clear negation.")
    if not disclaimer:
        return Finding("Finance integrity", "watch", "No educational/advice boundary detected in the script.")
    return Finding("Finance integrity", "pass", "No obvious advice or guaranteed-return language detected.")


def assess_repetition(text: str) -> Finding:
    sentence_list = sentences(text)
    starts: dict[str, int] = {}
    for sentence in sentence_list:
        first = " ".join(words(sentence.lower())[:3])
        if first:
            starts[first] = starts.get(first, 0) + 1
    repeated = {start: count for start, count in starts.items() if count >= 4}
    if repeated:
        detail = ", ".join(f"{start} ({count})" for start, count in sorted(repeated.items(), key=lambda item: -item[1])[:5])
        return Finding("Repetition", "watch", f"Repeated sentence openings may create a patterned read: {detail}.")
    return Finding("Repetition", "pass", "No obvious repeated sentence-opening pattern detected.")


def review(text: str) -> list[Finding]:
    return [
        assess_hook(text),
        assess_story(text),
        assess_pacing(text),
        assess_ai_language(text),
        assess_voice(text),
        assess_finance_integrity(text),
        assess_repetition(text),
    ]


def render_markdown(project: str, source_path: Path, text: str, findings: list[Finding]) -> str:
    total = sum(score(finding.status) for finding in findings)
    max_total = len(findings) * 2
    fail_count = sum(1 for finding in findings if finding.status == "fail")
    watch_count = sum(1 for finding in findings if finding.status == "watch")
    verdict = "Approved for next production step"
    if fail_count:
        verdict = "Needs revision before media generation"
    elif watch_count >= 3:
        verdict = "Usable, but revise before final production"

    word_count = len(words(text))
    sentence_count = len(sentences(text))
    paragraph_count = len(paragraphs(text))

    lines = [
        "# Script Story Quality Review",
        "",
        f"- Project: `{project}`",
        f"- Source: `{source_path.as_posix()}`",
        f"- Verdict: **{verdict}**",
        f"- Score: **{total}/{max_total}**",
        f"- Length: {word_count} words, {sentence_count} sentences, {paragraph_count} paragraphs",
        "",
        "## Findings",
        "",
    ]
    for finding in findings:
        marker = {"pass": "PASS", "watch": "WATCH", "fail": "FAIL"}[finding.status]
        lines.append(f"- **{marker} - {finding.label}:** {finding.detail}")

    lines.extend(
        [
            "",
            "## Required Human Pass",
            "",
            "This checker is heuristic. Before image or audio generation, still read the first 60 seconds aloud and ask:",
            "",
            "1. Would someone who does not know Roman care?",
            "2. Are we making the viewer experience the moment, not just receive facts?",
            "3. Did the script invent anything that was not provided?",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_source(project_dir: Path, source_name: str) -> Path:
    source = project_dir / source_name
    if source.exists():
        return source
    raise FileNotFoundError(f"Script source not found: {source}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Review Roman Financial script storytelling quality.")
    parser.add_argument("--project", required=True, help="Episode slug under projects/.")
    parser.add_argument("--source", default="voiceover.txt", help="Script file inside the episode folder.")
    parser.add_argument(
        "--output",
        default=None,
        help="Review output path. Defaults to projects/<slug>/work/reviews/script_story_quality.md.",
    )
    parser.add_argument("--fail-on-needs-revision", action="store_true", help="Exit 1 when any check fails.")
    args = parser.parse_args()

    project_dir = ROOT / "projects" / args.project
    if not project_dir.exists():
        raise FileNotFoundError(f"Project not found: {project_dir}")

    source_path = resolve_source(project_dir, args.source)
    text = source_path.read_text(encoding="utf-8")
    findings = review(text)

    output_path = Path(args.output) if args.output else project_dir / "work" / "reviews" / "script_story_quality.md"
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(args.project, source_path.relative_to(ROOT), text, findings), encoding="utf-8")

    print(f"Wrote: {output_path}")
    for finding in findings:
        print(f"{finding.status.upper():5} {finding.label}: {finding.detail}")

    if args.fail_on_needs_revision and any(finding.status == "fail" for finding in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
