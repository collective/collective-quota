"""Module where all interfaces, events and exceptions live."""

from collective.quota import _
from plone.restapi.controlpanels.interfaces import IControlpanel
from plone.restapi.interfaces import IPloneRestapiLayer
from zope import schema
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IBrowserLayer(IDefaultBrowserLayer):
    """Classic UI layer."""


class IQuotaRestapiLayer(IPloneRestapiLayer):
    """REST layer: overrides of plone.restapi adapters are registered for it."""


class IQuotaSettings(Interface):
    """Quota settings stored in the registry (prefix ``collective.quota``).

    Every record defaults to ``None``, meaning "not set in the control panel":
    the environment variable or the built-in default applies instead (see
    ``collective.quota.settings``). Invariants are checked on the effective
    values by the control panel, not here.
    """

    soft_limit_mb = schema.Int(
        title=_("Soft limit (MB)"),
        description=_(
            "When total usage reaches this value, editors see a warning. "
            "0 disables the warning. Leave empty to use the environment "
            "variable or the default."
        ),
        min=0,
        required=False,
    )

    hard_limit_mb = schema.Int(
        title=_("Hard limit (MB)"),
        description=_(
            "When a save would push total usage above this value, the policy "
            "below applies. 0 disables enforcement. Leave empty to use the "
            "environment variable or the default."
        ),
        min=0,
        required=False,
    )

    over_limit_policy = schema.Choice(
        title=_("Policy when the hard limit is reached"),
        description=_("Leave empty to use the environment variable or the default."),
        vocabulary="collective.quota.OverLimitPolicies",
        required=False,
    )

    max_file_size_mb = schema.Int(
        title=_("Maximum file size over the limit (MB)"),
        description=_(
            'Only used by the policy "Allow uploads up to a maximum file size". '
            "Leave empty to use the environment variable or the default."
        ),
        min=0,
        required=False,
    )


class IQuotaControlpanel(IControlpanel):
    """Marker for the quota REST control panel adapter."""
