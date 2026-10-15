"""Registry records, built-in defaults, vocabulary and invariants."""

from collective.quota import PACKAGE_NAME
from collective.quota import settings as settings_module
from collective.quota.policy import POLICIES
from collective.quota.settings import DEFAULTS
from collective.quota.settings import FIELDS
from collective.quota.settings import get_registry_values
from collective.quota.settings import get_settings
from collective.quota.settings import MAX_FILE_REQUIRED
from collective.quota.settings import SOFT_ABOVE_HARD
from collective.quota.usage import get_settings as usage_get_settings
from collective.quota.usage import QuotaSettings as UsageQuotaSettings
from plone import api
from zope.component import getUtility
from zope.schema.interfaces import IVocabularyFactory

import pytest


MB = 1024 * 1024


class TestRegistry:
    def test_records_default_to_none_after_install(self, portal):
        for name in FIELDS:
            assert api.portal.get_registry_record(f"collective.quota.{name}") is None

    def test_builtin_defaults_when_nothing_set(self, portal):
        settings = get_settings()
        assert settings.soft_bytes == 0
        assert settings.hard_bytes == 0
        assert settings.policy == "block_all"
        assert settings.max_file_bytes == 10 * MB
        assert settings.sources == dict.fromkeys(FIELDS, "default")
        assert settings.locked == frozenset()
        assert settings.values == DEFAULTS

    def test_get_settings_converts_mb_to_bytes(self, portal, set_quota):
        set_quota(soft_mb=80, hard_mb=100, policy="limit_file_size", max_file_mb=5)
        settings = get_settings()
        assert settings.soft_bytes == 80 * MB
        assert settings.hard_bytes == 100 * MB
        assert settings.policy == "limit_file_size"
        assert settings.max_file_bytes == 5 * MB
        assert settings.sources == dict.fromkeys(FIELDS, "registry")
        assert settings.values == {
            "soft_limit_mb": 80,
            "hard_limit_mb": 100,
            "over_limit_policy": "limit_file_size",
            "max_file_size_mb": 5,
        }

    def test_get_settings_without_records_is_safe(self, portal, installer):
        installer.uninstall_product(PACKAGE_NAME)
        assert get_registry_values() == dict.fromkeys(FIELDS)
        assert get_settings().sources == dict.fromkeys(FIELDS, "default")

    def test_registry_none_treated_as_unset(self, portal, set_quota):
        set_quota(soft_mb=None, hard_mb=100, policy=None, max_file_mb=None)
        settings = get_settings()
        assert settings.sources == {
            "soft_limit_mb": "default",
            "hard_limit_mb": "registry",
            "over_limit_policy": "default",
            "max_file_size_mb": "default",
        }

    def test_usage_reexports(self):
        assert usage_get_settings is get_settings
        assert UsageQuotaSettings is settings_module.QuotaSettings


class TestVocabulary:
    def test_vocabulary_terms(self, portal):
        factory = getUtility(IVocabularyFactory, "collective.quota.OverLimitPolicies")
        vocabulary = factory(portal)
        assert [term.token for term in vocabulary] == list(POLICIES)
        assert [term.value for term in vocabulary] == list(POLICIES)
        assert vocabulary.getTerm("allow").title == (
            "Allow everything, only show warnings"
        )


class TestInvariants:
    def _resolved(self, source="registry", **values):
        merged = {**DEFAULTS, **values}
        return {name: (merged[name], source) for name in FIELDS}

    @pytest.mark.parametrize(
        "values,expected",
        [
            ({}, []),
            ({"soft_limit_mb": 100, "hard_limit_mb": 100}, []),
            ({"soft_limit_mb": 101, "hard_limit_mb": 100}, [SOFT_ABOVE_HARD]),
            ({"soft_limit_mb": 500, "hard_limit_mb": 0}, []),
            ({"over_limit_policy": "limit_file_size"}, []),
            (
                {"over_limit_policy": "limit_file_size", "max_file_size_mb": 0},
                [MAX_FILE_REQUIRED],
            ),
            ({"over_limit_policy": "allow", "max_file_size_mb": 0}, []),
        ],
    )
    def test_find_violations(self, values, expected):
        violations = settings_module.find_violations(self._resolved(**values))
        assert [message for message, _names in violations] == expected

    def test_invariant_errors_ignore_environment_only_conflicts(self):
        resolved = self._resolved(source="env", soft_limit_mb=200, hard_limit_mb=100)
        assert settings_module.invariant_errors(resolved) == []
        resolved["soft_limit_mb"] = (200, "registry")
        assert settings_module.invariant_errors(resolved) == [SOFT_ABOVE_HARD]
