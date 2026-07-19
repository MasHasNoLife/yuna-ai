from yuna.core.fact_extractor import (
    MemoryOp,
    build_prompt,
    is_junk_fact,
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


# ── New typed operations ─────────────────────────────────────────────────────


def test_event_extraction():
    ops = parse_operations("[EVENT] Mas started learning to cook pasta.")
    assert ops == [MemoryOp("event", "Mas started learning to cook pasta.")]


def test_self_extraction():
    ops = parse_operations("[SELF] Yuna has gotten into charcoal drawing recently.")
    assert ops == [MemoryOp("self", "Yuna has gotten into charcoal drawing recently.")]


def test_build_prompt_includes_reply():
    prompt = build_prompt("Mas", "what are you up to?", "", "", "Just sketching all day!")
    assert "Just sketching all day!" in prompt


# ── Junk filtering (denials + conversation meta-states) ─────────────────────


def test_junk_denials_detected():
    assert is_junk_fact("There is no robot and laser game project.")
    assert is_junk_fact("The project does not exist.")
    assert is_junk_fact("That never happened.")


def test_junk_meta_states_detected():
    assert is_junk_fact("Mas is unsure what coding thing Yuna is referring to.")
    assert is_junk_fact("Mas believes Yuna may have summoned him.")
    assert is_junk_fact("Saad asked Yuna what they are doing.")
    assert is_junk_fact("Mas is doing well and asking about Yuna's activities.")
    assert is_junk_fact("Mas is open to discussing various topics.")


def test_real_facts_not_junk():
    assert not is_junk_fact("Mas's favorite dish is carbonara.")
    assert not is_junk_fact("Mas plays League of Legends and Osu.")
    assert not is_junk_fact("Mas is trying to make a research paper.")
    assert not is_junk_fact("Yuna's nickname is tuna.")


def test_parse_filters_junk_facts():
    ops = parse_operations(
        "[FACT] There is no robot and laser game project.\n[FACT] Mas loves carbonara."
    )
    assert ops == [MemoryOp("fact", "Mas loves carbonara.")]


def test_parse_allows_forget_of_junk_shaped_fact():
    # FORGET targets an existing stored fact — the junk filter must not block it
    ops = parse_operations("[FORGET] There is no robot and laser game project.")
    assert len(ops) == 1
    assert ops[0].kind == "forget"


def test_build_prompt_includes_today():
    prompt = build_prompt("Mas", "i ran a race last saturday", "", "", today="25 May 2023")
    assert "25 May 2023" in prompt
    # unknown when not provided
    assert "unknown" in build_prompt("Mas", "hello there friend", "", "")
