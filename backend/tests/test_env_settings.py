"""Environment variables, the lock flag and their resolution."""

from collective.quota import settings as settings_module
from collective.quota.settings import FIELDS
from collective.quota.settings import get_settings
from collective.quota.settings import is_locked
from collective.quota.settings import read_env

import logging
import pytest


MB = 1024 * 1024


@pytest.fixture(autouse=True)
def _fresh_warnings(monkeypatch):
    monkeypatch.setattr(settings_module, "_warned", set())


ENV_CASES = [
    ("soft", "soft_limit_mb", "50", 50),
    ("hard", "hard_limit_mb", "100", 100),
    ("policy", "over_limit_policy", "allow", "allow"),
    ("max_file", "max_file_size_mb", "3", 3),
]


class TestEnvironment:
    @pytest.mark.parametrize("arg,name,raw,value", ENV_CASES)
    def test_env_values_used_when_registry_unset(
        self, portal, quota_env, arg, name, raw, value
    ):
        quota_env(**{arg: raw})
        settings = get_settings()
        assert settings.values[name] == value
        assert settings.sources[name] == "env"
        assert settings.locked == frozenset()

    def test_env_converted_to_bytes(self, portal, quota_env):
        quota_env(soft=1, hard=2, policy="block_files", max_file=3)
        settings = get_settings()
        assert (settings.soft_bytes, settings.hard_bytes, settings.max_file_bytes) == (
            1 * MB,
            2 * MB,
            3 * MB,
        )
        assert settings.policy == "block_files"

    def test_registry_overrides_env_when_not_locked(self, portal, quota_env, set_quota):
        quota_env(soft=1, hard=2, policy="allow", max_file=3)
        set_quota(soft_mb=10, hard_mb=20, policy="block_files", max_file_mb=30)
        settings = get_settings()
        assert settings.sources == dict.fromkeys(FIELDS, "registry")
        assert settings.hard_bytes == 20 * MB
        assert settings.policy == "block_files"

    def test_lock_makes_env_win_over_registry(self, portal, quota_env, set_quota):
        quota_env(hard=100, policy="allow", lock="1")
        set_quota(soft_mb=10, hard_mb=20, policy="block_files", max_file_mb=30)
        settings = get_settings()
        assert settings.hard_bytes == 100 * MB
        assert settings.policy == "allow"
        assert settings.sources == {
            "soft_limit_mb": "registry",
            "hard_limit_mb": "env-locked",
            "over_limit_policy": "env-locked",
            "max_file_size_mb": "registry",
        }
        assert settings.locked == {"hard_limit_mb", "over_limit_policy"}

    def test_lock_without_env_value_leaves_field_editable(self, portal, quota_env):
        quota_env(lock="yes")
        settings = get_settings()
        assert settings.locked == frozenset()
        assert settings.sources == dict.fromkeys(FIELDS, "default")
        assert not is_locked("hard_limit_mb")

    @pytest.mark.parametrize(
        "raw,locked",
        [
            ("1", True),
            ("true", True),
            ("TRUE", True),
            ("yes", True),
            ("on", True),
            (" On ", True),
            ("0", False),
            ("false", False),
            ("", False),
            ("garbage", False),
        ],
    )
    def test_lock_truthy_values(self, raw, locked):
        env = read_env({
            "COLLECTIVE_QUOTA_HARD_LIMIT_MB": "5",
            "COLLECTIVE_QUOTA_LOCK_SETTINGS": raw,
        })
        assert env.lock is locked
        assert is_locked("hard_limit_mb", env) is locked

    def test_invalid_int_and_policy_logged_and_ignored(self, caplog):
        environ = {
            "COLLECTIVE_QUOTA_HARD_LIMIT_MB": "lots",
            "COLLECTIVE_QUOTA_OVER_LIMIT_POLICY": "nope",
            "COLLECTIVE_QUOTA_SOFT_LIMIT_MB": "7",
        }
        with caplog.at_level(logging.WARNING, logger="collective.quota"):
            for _i in range(3):
                env = read_env(environ)
        assert env.values == {"soft_limit_mb": 7}
        messages = [r.getMessage() for r in caplog.records]
        assert messages == [
            "Ignoring COLLECTIVE_QUOTA_HARD_LIMIT_MB='lots': expected an integer >= 0",
            "Ignoring COLLECTIVE_QUOTA_OVER_LIMIT_POLICY='nope': expected one of "
            "block_all, block_files, limit_file_size, allow",
        ]
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="collective.quota"):
            read_env({"COLLECTIVE_QUOTA_HARD_LIMIT_MB": "more"})
        assert len(caplog.records) == 1  # a different value is logged again

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_empty_string_is_unset(self, raw, caplog):
        with caplog.at_level(logging.WARNING, logger="collective.quota"):
            env = read_env({"COLLECTIVE_QUOTA_HARD_LIMIT_MB": raw})
        assert env.values == {}
        assert caplog.records == []

    def test_negative_int_ignored(self, caplog):
        with caplog.at_level(logging.WARNING, logger="collective.quota"):
            env = read_env({"COLLECTIVE_QUOTA_MAX_FILE_SIZE_MB": "-1"})
        assert env.values == {}
        assert len(caplog.records) == 1

    def test_reads_os_environ_by_default(self, quota_env):
        quota_env(hard=9, lock="on")
        env = read_env()
        assert env.values == {"hard_limit_mb": 9}
        assert env.lock is True

    def test_conflicting_env_values_logged_once_and_applied(
        self, portal, quota_env, caplog
    ):
        quota_env(soft=200, hard=100)
        with caplog.at_level(logging.WARNING, logger="collective.quota"):
            get_settings()
            settings = get_settings()
        assert settings.soft_bytes == 200 * MB
        assert [r.getMessage() for r in caplog.records] == [
            "Quota settings conflict (soft_limit_mb=200, hard_limit_mb=100): "
            "The soft limit cannot be higher than the hard limit."
        ]
