import os

import pytest

from yida_ai.config.settings import SettingsStore
from yida_ai.security import DPAPIProtector, SecretStore


class ReverseProtector:
    def protect(self, value):
        return b"protected:" + value[::-1]

    def unprotect(self, value):
        assert value.startswith(b"protected:")
        return value.removeprefix(b"protected:")[::-1]


def test_secret_store_never_writes_plaintext(tmp_path):
    secret = "sk-secret-fixture"
    store = SecretStore(tmp_path / "api-key.dpapi", ReverseProtector())
    store.save(secret)
    assert secret.encode() not in store.path.read_bytes()
    assert store.load() == secret
    store.clear()
    assert not store.exists


@pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")
def test_dpapi_current_user_round_trip(tmp_path):
    secret = "yida-dpapi-round-trip-fixture"
    store = SecretStore(tmp_path / "api-key.dpapi", DPAPIProtector())
    store.save(secret)
    assert secret.encode() not in store.path.read_bytes()
    assert SecretStore(store.path, DPAPIProtector()).load() == secret


def test_settings_store_loads_saved_secret_after_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("YIDA_AI_API_KEY", raising=False)
    secret_file = tmp_path / "api-key.dpapi"
    first = SettingsStore(
        tmp_path / "config.json",
        tmp_path,
        SecretStore(secret_file, ReverseProtector()),
    )
    first.save_api_key("restart-secret")
    second = SettingsStore(
        tmp_path / "config.json",
        tmp_path,
        SecretStore(secret_file, ReverseProtector()),
    )
    assert second.load_api_key() == "restart-secret"
