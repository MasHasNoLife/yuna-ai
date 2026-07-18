"""Emotion-tag parsing for Yuna's responses. Pure functions, no dependencies.

Yuna's LLM output embeds performance tags like:
    "[happy] That's great! [smug] Obviously I knew it."
The pipeline splits on these to drive TTS speed and avatar expressions.
"""

from __future__ import annotations

import re

TAG_PATTERN = re.compile(r"\[(.*?)\]\s*")


def strip_tags(text: str) -> str:
    """Remove all [tags], collapse leftover double spaces."""
    clean = TAG_PATTERN.sub("", text).strip()
    return re.sub(r"  +", " ", clean)


def first_tag(text: str) -> str | None:
    """The first [tag] in the text, or None."""
    match = TAG_PATTERN.search(text)
    return match.group(1) if match else None


def split_segments(text: str) -> list[tuple[str | None, str]]:
    """Split text into (tag, segment) pairs.

    Text before the first tag gets tag None; each tag applies to the text
    that follows it until the next tag. Empty segments are dropped.

    "[happy] Hi there [sad] bye" -> [("happy", "Hi there"), ("sad", "bye")]
    """
    segments: list[tuple[str | None, str]] = []
    last_idx = 0
    current_tag: str | None = None

    for match in TAG_PATTERN.finditer(text):
        segment_text = text[last_idx : match.start()].strip()
        if segment_text:
            segments.append((current_tag, segment_text))
        current_tag = match.group(1).lower()
        last_idx = match.end()

    segment_text = text[last_idx:].strip()
    if segment_text:
        segments.append((current_tag, segment_text))
    return segments


def normalize_for_tts(text: str) -> str:
    """Fix pronunciations and formatting quirks before synthesis."""
    # Expressive sounds Kokoro would spell out letter-by-letter
    text = re.sub(r"\b[Hh]mph\b", "humph", text)
    text = re.sub(r"\b[Pp]fft\b", "puf", text)
    text = re.sub(r"\b[Tt]ch\b", "tsk", text)
    # Asterisk emphasis -> quotes (ALL CAPS reads as an acronym; quotes inflect)
    text = re.sub(r"\*(.*?)\*", r"'\1'", text)
    return text
