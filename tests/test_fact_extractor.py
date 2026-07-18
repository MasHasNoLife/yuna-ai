from yuna.core.fact_extractor import (
    MemoryOp,
    build_prompt,
    is_worth_extracting,
    parse_operations,
)


def test_none_response_yields_no_ops():
    assert parse_operations("NONE") == []
    assert parse_operations("The answer is NONE here") == []
    assert parse_operations("") == []
    assert parse_operations(None) == []


def test_fact_extraction():
    ops = parse_operations("[FACT] Mas loves the color neon green.")
    assert ops == [MemoryOp("fact", "Mas loves the color neon green.")]


def test_multiple_facts_multiline():
    ops = parse_operations("[FACT] Mas has a sister.\n[FACT] The sister lives in Sweden.")
    assert len(ops) == 2
    assert all(op.kind == "fact" for op in ops)


def test_update_operation():
    ops = parse_operations("[UPDATE] Mas likes red -> Mas likes blue")
    assert ops == [MemoryOp("update", "Mas likes red", "Mas likes blue")]


def test_malformed_update_ignored():
    assert parse_operations("[UPDATE] no arrow here") == []


def test_forget_operation():
    ops = parse_operations("[FORGET] Mas likes red")
    assert ops == [MemoryOp("forget", "Mas likes red")]


def test_bullet_decorations_stripped():
    ops = parse_operations("- [FACT] Decorated fact.")
    assert ops == [MemoryOp("fact", "Decorated fact.")]


def test_untagged_chatter_ignored():
    assert parse_operations("Sure! Here is a fact about the user.") == []


def test_build_prompt_fills_placeholders():
    prompt = build_prompt("Mas", "my dog is called Rex", "User: hi", "Mas has a cat")
    assert "Mas" in prompt
    assert "my dog is called Rex" in prompt
    assert "Mas has a cat" in prompt


def test_build_prompt_empty_context_becomes_none():
    prompt = build_prompt("Mas", "hello there general kenobi", "", "")
    assert "None" in prompt


def test_is_worth_extracting():
    assert not is_worth_extracting("lol")
    assert not is_worth_extracting("yes ok sure")
    assert is_worth_extracting("my favorite color is neon green")
