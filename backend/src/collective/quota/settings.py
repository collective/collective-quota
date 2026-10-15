"""Effective quota settings: registry + environment variables + lock flag.

Resolution per field (see specs/00-architecture.md, §3.3)::

    locked (lock flag on and variable set) -> environment value, "env-locked"
    registry record is not None             -> registry value,    "registry"
    variable set                            -> environment value, "env"
    otherwise                               -> built-in default,  "default"

Variables are read from ``os.environ`` on every call; nothing is cached.
"""

from collective.quota import _
from collective.quota import logger
from collective.quota.policy import LIMIT_FILE_SIZE
from collective.quota.policy import POLICIES
from collective.quota.utils import mb_to_bytes
from dataclasses import dataclass
from dataclasses import field
from plone import api
from plone.registry.interfaces import IRegistry
from zope.component import getUtility

import os


REGISTRY_PREFIX = "collective.quota"

ENV_VARS = {
    "soft_limit_mb": "COLLECTIVE_QUOTA_SOFT_LIMIT_MB",
    "hard_limit_mb": "COLLECTIVE_QUOTA_HARD_LIMIT_MB",
    "over_limit_policy": "COLLECTIVE_QUOTA_OVER_LIMIT_POLICY",
    "max_file_size_mb": "COLLECTIVE_QUOTA_MAX_FILE_SIZE_MB",
}
LOCK_VAR = "COLLECTIVE_QUOTA_LOCK_SETTINGS"
TRUTHY = frozenset({"1", "true", "yes", "on"})

DEFAULTS = {
    "soft_limit_mb": 0,
    "hard_limit_mb": 0,
    "over_limit_policy": "block_all",
    "max_file_size_mb": 10,
}
FIELDS = tuple(ENV_VARS)
INT_FIELDS = frozenset({"soft_limit_mb", "hard_limit_mb", "max_file_size_mb"})

SOURCE_ENV_LOCKED = "env-locked"
SOURCE_REGISTRY = "registry"
SOURCE_ENV = "env"
SOURCE_DEFAULT = "default"

SOFT_ABOVE_HARD = _("The soft limit cannot be higher than the hard limit.")
MAX_FILE_REQUIRED = _("Set a maximum file size greater than 0 for this policy.")

# (variable, value) pairs and invariant violations already logged.
_warned: set = set()


def _warn_once(key, message, *args):
    if key in _warned:
        return
    _warned.add(key)
    logger.warning(message, *args)


def _parse(name: str, raw: str) -> int | str | None:
    """Parse one environment value; log and return None when invalid."""
    var = ENV_VARS[name]
    if name in INT_FIELDS:
        try:
            value = int(raw)
        except ValueError:
            value = -1
        if value >= 0:
            return value
        _warn_once((var, raw), "Ignoring %s=%r: expected an integer >= 0", var, raw)
        return None
    if raw in POLICIES:
        return raw
    _warn_once(
        (var, raw),
        "Ignoring %s=%r: expected one of %s",
        var,
        raw,
        ", ".join(POLICIES),
    )
    return None


@dataclass(frozen=True)
class EnvSettings:
    values: dict  # field -> parsed value; only variables that are set and valid
    lock: bool


def read_env(environ=None) -> EnvSettings:
    environ = os.environ if environ is None else environ
    values = {}
    for name, var in ENV_VARS.items():
        raw = environ.get(var, "").strip()
        if not raw:
            continue
        value = _parse(name, raw)
        if value is not None:
            values[name] = value
    lock = environ.get(LOCK_VAR, "").strip().lower() in TRUTHY
    return EnvSettings(values=values, lock=lock)


def is_locked(name: str, env: EnvSettings | None = None) -> bool:
    env = env if env is not None else read_env()
    return env.lock and name in env.values


def resolve(name: str, registry_value, env: EnvSettings) -> tuple:
    """Return ``(effective value, source)`` for one field."""
    if is_locked(name, env):
        return env.values[name], SOURCE_ENV_LOCKED
    if registry_value is not None:
        return registry_value, SOURCE_REGISTRY
    if name in env.values:
        return env.values[name], SOURCE_ENV
    return DEFAULTS[name], SOURCE_DEFAULT


def resolve_all(registry_values: dict, env: EnvSettings) -> dict:
    """``{field: (effective value, source)}`` for every field."""
    return {name: resolve(name, registry_values.get(name), env) for name in FIELDS}


def find_violations(resolved: dict) -> list:
    """Invariants on effective values: ``[(message, fields), ...]``.

    A soft or hard limit of 0 is disabled, so it never conflicts.
    """
    values = {name: value for name, (value, _source) in resolved.items()}
    violations = []
    soft, hard = values["soft_limit_mb"], values["hard_limit_mb"]
    if soft and hard and soft > hard:
        violations.append((SOFT_ABOVE_HARD, ("soft_limit_mb", "hard_limit_mb")))
    if (
        values["over_limit_policy"] == LIMIT_FILE_SIZE
        and not values["max_file_size_mb"]
    ):
        violations.append((
            MAX_FILE_REQUIRED,
            ("over_limit_policy", "max_file_size_mb"),
        ))
    return violations


def invariant_errors(resolved: dict) -> list:
    """Violations a control panel save must reject.

    Only violations that involve a value set in the control panel count:
    combinations coming purely from the environment (or defaults) belong to
    the operator and are logged by ``get_settings()`` instead.
    """
    return [
        message
        for message, names in find_violations(resolved)
        if any(resolved[name][1] == SOURCE_REGISTRY for name in names)
    ]


@dataclass(frozen=True)
class QuotaSettings:
    soft_bytes: int
    hard_bytes: int
    policy: str
    max_file_bytes: int
    sources: dict[str, str] = field(default_factory=dict)
    locked: frozenset[str] = frozenset()
    values: dict = field(default_factory=dict)  # field -> effective value (MB/token)


def get_registry_values() -> dict:
    """Registry values per field; all None when the records do not exist."""
    return {
        name: api.portal.get_registry_record(f"{REGISTRY_PREFIX}.{name}", default=None)
        for name in FIELDS
    }


def set_registry_value(name: str, value) -> None:
    """Store one setting; ``None`` clears it (plone.api refuses ``None``)."""
    getUtility(IRegistry)[f"{REGISTRY_PREFIX}.{name}"] = value


def get_settings() -> QuotaSettings:
    env = read_env()
    resolved = resolve_all(get_registry_values(), env)
    for message, names in find_violations(resolved):
        current = tuple((name, resolved[name][0]) for name in names)
        _warn_once(
            ("invariant", current),
            "Quota settings conflict (%s): %s",
            ", ".join(f"{name}={value}" for name, value in current),
            message,
        )
    values = {name: value for name, (value, _source) in resolved.items()}
    return QuotaSettings(
        soft_bytes=mb_to_bytes(values["soft_limit_mb"]),
        hard_bytes=mb_to_bytes(values["hard_limit_mb"]),
        policy=values["over_limit_policy"],
        max_file_bytes=mb_to_bytes(values["max_file_size_mb"]),
        sources={name: source for name, (_value, source) in resolved.items()},
        locked=frozenset(name for name in FIELDS if is_locked(name, env)),
        values=values,
    )
