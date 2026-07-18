from yuna.core.metrics import MetricsHub


def _make_hub_turn(hub, **kwargs):
    rec = hub.new_turn(username="Mas")
    for k, v in kwargs.items():
        setattr(rec, k, v)
    return rec


def test_turn_numbering_increments():
    hub = MetricsHub()
    assert hub.new_turn().turn == 1
    assert hub.new_turn().turn == 2


def test_finish_updates_totals(tmp_path, monkeypatch):
    hub = MetricsHub()
    rec = _make_hub_turn(hub, memory_ops=["+fact", "~update", "-forget"], error="boom")
    # Avoid touching the real data dir
    monkeypatch.setattr(hub, "_append_jsonl", lambda r: None)
    hub.finish(rec)
    assert hub.totals["turns"] == 1
    assert hub.totals["errors"] == 1
    assert hub.totals["memory_facts"] == 1
    assert hub.totals["memory_updates"] == 1
    assert hub.totals["memory_forgets"] == 1


def test_snapshot_averages(monkeypatch):
    hub = MetricsHub()
    monkeypatch.setattr(hub, "_append_jsonl", lambda r: None)
    for ttft in (100.0, 300.0):
        rec = _make_hub_turn(hub, ttft_ms=ttft)
        hub.finish(rec)
    snap = hub.snapshot()
    assert snap["averages"]["ttft_ms"] == 200.0
    assert snap["totals"]["turns"] == 2
    assert len(snap["turns"]) == 2


def test_summary_contains_key_fields():
    hub = MetricsHub()
    rec = _make_hub_turn(
        hub,
        llm_backend="google/gemma-4",
        ttft_ms=1500.0,
        tok_per_s=42.0,
        recalled=2,
        memory_ops=["+fact"],
        tts_backend="kokoro",
        ttfa_ms=800.0,
    )
    s = rec.summary()
    assert "ttft=1.50s" in s
    assert "42tok/s" in s
    assert "recall=2" in s
    assert "tts=kokoro" in s
