"""Pure helpers for the reaction pipeline: timeline merging and script parsing."""

from __future__ import annotations


def build_timeline(
    descriptions: list[tuple[float, str]],
    audio_segments: list[tuple[float, str]] | None,
) -> str:
    """Interleave visual descriptions and speech segments by timestamp.

    descriptions: [(seconds, text)] — text may already carry an "[Ns]" prefix.
    audio_segments: [(seconds, transcript)] or None.
    Returns the newline-joined timeline Yuna reacts to, in chronological order.
    """
    timeline: list[tuple[float, str]] = list(descriptions)
    if audio_segments:
        for start_sec, text in audio_segments:
            timeline.append((start_sec, f'[SPEECH] "{text}"'))

    timeline.sort(key=lambda x: x[0])

    parts = []
    for ts, entry in timeline:
        if entry.startswith("["):
            parts.append(entry)
        else:
            parts.append(f"[{int(ts)}s] {entry}")
    return "\n".join(parts)


def extract_dialogue_lines(script_text: str) -> list[str]:
    """Dialogue lines from a generated reaction script, skipping
    [TIMESTAMP ...] / [DESCRIPTOR ...] markers and blank lines.
    """
    lines = []
    for line in script_text.splitlines():
        line = line.strip()
        if not line or line.startswith("[TIMESTAMP") or line.startswith("[DESCRIPTOR"):
            continue
        lines.append(line)
    return lines


def numbered_output_path(directory, stem: str, suffix: str = ".txt"):
    """First non-existing '<stem><n><suffix>' path in directory (stem, stem1, stem2...)."""
    from pathlib import Path

    directory = Path(directory)
    candidate = directory / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}{counter}{suffix}"
        counter += 1
    return candidate
