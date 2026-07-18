"""Emotion blueprints: tag -> Live2D parameter targets + physics/speech speed.

Pure data + resolution logic (unit-testable); vts_link consumes the targets,
tts consumes the speech speeds.
"""

from __future__ import annotations

# Verified default parameter names for the Hiyori model (see scripts/vts_diag.py):
# FaceAngleX/Y/Z (-30..30), MouthOpen (0..1), MouthSmile (0..1),
# EyeOpenLeft/Right (0..1), EyeLeftX/Y EyeRightX/Y (-1..1),
# BrowLeftY/RightY (0..1), FaceAngry (0..1), CheekPuff (0..1)

EMOTION_BLUEPRINTS: dict[str, dict] = {
    # Happy / Laughing
    "happy": {"speed": 1.5, "MouthSmile": 1.0},
    "laugh": {"speed": 2.0, "MouthSmile": 1.0, "EyeOpenLeft": 0.2, "EyeOpenRight": 0.2},
    "giggle": {"speed": 1.8, "MouthSmile": 0.9, "EyeOpenLeft": 0.5, "EyeOpenRight": 0.5},
    "excited": {"speed": 2.5, "MouthSmile": 1.0, "BrowLeftY": 0.9, "BrowRightY": 0.9},
    "chuckles": {"speed": 1.3, "MouthSmile": 0.8},
    "smiles slightly": {"speed": 1.0, "MouthSmile": 0.5},
    # Sad / Crying
    "sad": {
        "speed": 0.4,
        "MouthSmile": 0.0,
        "FaceAngleZ": -10.0,
        "BrowLeftY": 0.5,
        "BrowRightY": 0.5,
    },
    "crying": {
        "speed": 0.3,
        "MouthSmile": 0.0,
        "EyeOpenLeft": 0.3,
        "EyeOpenRight": 0.3,
        "FaceAngleZ": -15.0,
    },
    "concerned": {"speed": 0.7, "BrowLeftY": 0.6, "BrowRightY": 0.6},
    # Angry / Annoyed / Pouty
    "angry": {"speed": 1.8, "FaceAngry": 1.0, "BrowLeftY": 0.1, "BrowRightY": 0.1},
    "hmph": {"speed": 1.3, "FaceAngleX": 12.0, "FaceAngry": 0.7},
    "pouty": {"speed": 1.2, "FaceAngleX": 8.0, "FaceAngry": 0.3, "CheekPuff": 1.0},
    "mad": {"speed": 2.0, "FaceAngry": 1.0, "BrowLeftY": 0.0, "BrowRightY": 0.0},
    "scoff": {"speed": 1.3, "FaceAngry": 0.6, "EyeOpenLeft": 0.4, "EyeOpenRight": 0.4},
    "annoyed": {"speed": 1.2, "FaceAngry": 0.5},
    "smug": {"speed": 1.2, "MouthSmile": 1.0, "EyeOpenLeft": 0.5, "EyeOpenRight": 0.5},
    # Surprised / Shocked
    "surprised": {
        "speed": 1.2,
        "EyeOpenLeft": 1.0,
        "EyeOpenRight": 1.0,
        "BrowLeftY": 0.9,
        "BrowRightY": 0.9,
    },
    "shock": {
        "speed": 1.5,
        "EyeOpenLeft": 1.0,
        "EyeOpenRight": 1.0,
        "BrowLeftY": 1.0,
        "BrowRightY": 1.0,
    },
    "gasp": {"speed": 1.5, "EyeOpenLeft": 1.0, "EyeOpenRight": 1.0, "MouthOpen": 0.6},
    # Confused / Thinking
    "confused": {"speed": 0.8, "BrowLeftY": 0.6, "BrowRightY": 0.3, "FaceAngleZ": 5.0},
    "thinking": {
        "speed": 0.5,
        "EyeOpenLeft": 0.7,
        "EyeOpenRight": 0.7,
        "FaceAngleZ": 6.0,
        "EyeLeftX": 0.4,
        "EyeRightX": 0.4,
        "EyeLeftY": 0.3,
        "EyeRightY": 0.3,
    },
    "curious": {"speed": 1.0, "FaceAngleZ": 5.0, "BrowLeftY": 0.7, "BrowRightY": 0.7},
    # Flustered / Shy
    "flustered": {"speed": 2.0, "FaceAngleY": -5.0, "MouthSmile": 0.3},
    "embarrassed": {"speed": 1.5, "FaceAngleY": -8.0, "MouthSmile": 0.2},
    "shy": {
        "speed": 1.0,
        "FaceAngleY": -8.0,
        "MouthSmile": 0.3,
        "EyeOpenLeft": 0.6,
        "EyeOpenRight": 0.6,
    },
    "tease": {"speed": 1.2, "MouthSmile": 0.9, "EyeOpenLeft": 0.7, "EyeOpenRight": 0.7},
    # Bored / Tired / Relieved
    "bored": {"speed": 0.5, "EyeOpenLeft": 0.4, "EyeOpenRight": 0.4},
    "tired": {"speed": 0.3, "EyeOpenLeft": 0.3, "EyeOpenRight": 0.3},
    "sigh": {"speed": 0.8, "EyeOpenLeft": 0.3, "EyeOpenRight": 0.3, "FaceAngleY": -3.0},
    "relieved": {
        "speed": 0.6,
        "MouthSmile": 0.4,
        "EyeOpenLeft": 0.6,
        "EyeOpenRight": 0.6,
        "FaceAngleY": -2.0,
    },
}

# Every Live2D parameter any emotion can touch (used to reset to neutral)
EMOTION_PARAMS: set[str] = {
    param for bp in EMOTION_BLUEPRINTS.values() for param in bp if param != "speed"
}

# Tags that mean "return to neutral" rather than an expression
NEUTRAL_TAGS = {"neutral", "none", "clear", "pauses slightly", "pauses", "playful tone"}

# Speech-rate modulation per tag family (used by TTS)
_SPEECH_SPEEDS = [
    (0.85, {"sad", "tired", "bored", "thinking", "confused", "concerned"}),
    (1.05, {"angry", "scoff", "hmph", "tease", "smug", "annoyed"}),
    (
        1.15,
        {
            "happy",
            "laugh",
            "giggle",
            "impressed",
            "surprised",
            "flustered",
            "embarrassed",
            "denial",
            "competitive",
        },
    ),
    (1.25, {"panic", "shock", "gasp", "excited"}),
]


def clean_tag(tag: str) -> str:
    return tag.lower().strip(" .!?-[]")


def resolve_blueprint(tag: str | None) -> dict | None:
    """Blueprint for a tag; fuzzy-matches ('laughing hard' -> 'laugh').

    Returns None for unknown tags and for neutral tags (caller resets state).
    """
    if not tag:
        return None
    clean = clean_tag(tag)
    if clean in NEUTRAL_TAGS:
        return None
    blueprint = EMOTION_BLUEPRINTS.get(clean)
    if blueprint is None:
        for name, bp in EMOTION_BLUEPRINTS.items():
            if name in clean:
                return bp
    return blueprint


def is_neutral(tag: str | None) -> bool:
    return tag is not None and clean_tag(tag) in NEUTRAL_TAGS


def speech_speed(tag: str | None) -> float:
    """Kokoro speaking-rate multiplier for a tag (1.0 = normal)."""
    if not tag:
        return 1.0
    clean = clean_tag(tag)
    for speed, tag_set in _SPEECH_SPEEDS:
        if clean in tag_set:
            return speed
    return 1.0
