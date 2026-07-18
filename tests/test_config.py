from yuna.core.config import Config, load_config


def test_defaults_without_file():
    cfg = load_config(path="/nonexistent/config.yaml")
    assert cfg.models.chat == "qwen2.5:14b"
    assert cfg.dashboard.host == "127.0.0.1"
    assert cfg.memory.recall_threshold == 0.35


def test_yaml_overrides(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "models:\n  chat: llama3:8b\nsampling:\n  temperature: 0.5\n", encoding="utf-8"
    )
    cfg = load_config(path=cfg_file)
    assert cfg.models.chat == "llama3:8b"
    assert cfg.sampling.temperature == 0.5
    # untouched sections keep defaults
    assert cfg.models.embedding == "nomic-embed-text"


def test_unknown_keys_ignored(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("models:\n  warp_drive: enabled\n", encoding="utf-8")
    cfg = load_config(path=cfg_file)  # must not raise
    assert isinstance(cfg, Config)


def test_paths_resolve_relative_to_root():
    cfg = load_config(path="/nonexistent/config.yaml")
    assert cfg.paths.memory == cfg.paths.data / "memory"
    assert cfg.paths.data.is_absolute()
