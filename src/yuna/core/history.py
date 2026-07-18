"""Conversation history helpers shared by the realtime chat and the Discord bot."""

from __future__ import annotations


def make_history(system_prompt: str) -> list[dict]:
    """Fresh message list containing only the system prompt."""
    return [{"role": "system", "content": system_prompt}]


def trim_history(messages: list[dict], max_messages: int) -> list[dict]:
    """Keep the system prompt plus the last `max_messages` messages.

    Never lets the window start on an orphaned assistant reply — the first
    kept message after the system prompt is always from the user.
    """
    if len(messages) <= max_messages + 1:
        return messages
    keep = messages[-max_messages:]
    if keep and keep[0].get("role") == "assistant":
        keep = keep[1:]
    return [messages[0]] + keep
