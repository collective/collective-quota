"""Classic control panel: ``@@quota-controlpanel``."""

from collective.quota import _
from collective.quota.interfaces import IQuotaSettings
from collective.quota.settings import ENV_VARS
from collective.quota.settings import FIELDS
from collective.quota.settings import get_registry_values
from collective.quota.settings import get_settings
from collective.quota.settings import INT_FIELDS
from collective.quota.settings import invariant_errors
from collective.quota.settings import read_env
from collective.quota.settings import REGISTRY_PREFIX
from collective.quota.settings import resolve_all
from collective.quota.settings import set_registry_value
from collective.quota.settings import SOURCE_DEFAULT
from collective.quota.settings import SOURCE_ENV
from collective.quota.settings import SOURCE_ENV_LOCKED
from collective.quota.settings import SOURCE_REGISTRY
from collective.quota.usage import get_usage_info
from collective.quota.usage import LEVEL_EXCEEDED
from collective.quota.usage import LEVEL_WARNING
from collective.quota.utils import human_readable_size
from collective.quota.vocabularies.policies import POLICY_TITLES
from html import escape
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from z3c.form import button
from z3c.form.interfaces import DISPLAY_MODE
from z3c.form.interfaces import IDataConverter
from z3c.form.interfaces import IErrorViewSnippet
from zope.component import getMultiAdapter
from zope.i18n import translate
from zope.interface import Invalid
from zope.schema import getFields


SOURCE_LABELS = {
    SOURCE_REGISTRY: _("Control panel"),
    SOURCE_ENV: _("Environment"),
    SOURCE_ENV_LOCKED: _("Environment (locked)"),
    SOURCE_DEFAULT: _("Default"),
}

SOURCE_BADGES = {
    SOURCE_REGISTRY: "text-bg-primary",
    SOURCE_ENV: "text-bg-info",
    SOURCE_ENV_LOCKED: "text-bg-dark",
    SOURCE_DEFAULT: "text-bg-secondary",
}

LEVEL_BARS = {
    LEVEL_EXCEEDED: "bg-danger",
    LEVEL_WARNING: "bg-warning",
}


def format_value(name, value):
    """Human-readable effective value: ``"500 MB"`` or the policy title."""
    if name in INT_FIELDS:
        return _("${size} MB", mapping={"size": value})
    return POLICY_TITLES.get(value, value)


def source_note(name, value, source):
    var = ENV_VARS[name]
    mapping = {"value": format_value(name, value), "variable": var}
    if source == SOURCE_ENV_LOCKED:
        return _(
            "Currently: ${value} (from environment variable ${variable}, locked).",
            mapping=mapping,
        )
    if source == SOURCE_ENV:
        return _(
            "Currently: ${value} (from environment variable ${variable}; "
            "a value saved here takes precedence).",
            mapping=mapping,
        )
    if source == SOURCE_REGISTRY:
        return _("Currently: ${value} (set in this control panel).", mapping=mapping)
    return _("Currently: ${value} (built-in default).", mapping=mapping)


class QuotaControlPanelForm(RegistryEditForm):
    schema = IQuotaSettings
    schema_prefix = REGISTRY_PREFIX
    label = _("Quota settings")
    description = _(
        "Limits apply to the bytes stored in file and image fields across the "
        "whole site."
    )

    buttons = RegistryEditForm.buttons.copy()
    handlers = RegistryEditForm.handlers.copy()

    def _translate(self, msg):
        return translate(msg, context=self.request)

    def updateFields(self):
        super().updateFields()
        self.quota_settings = get_settings()
        for name in self.quota_settings.locked:
            self.fields[name].mode = DISPLAY_MODE

    def updateWidgets(self):
        super().updateWidgets()
        settings = self.quota_settings
        for name in FIELDS:
            widget = self.widgets[name]
            value, source = settings.values[name], settings.sources[name]
            if name in settings.locked:
                # The registry value is irrelevant: show the environment value.
                widget.value = IDataConverter(widget).toWidgetValue(value)
            widget.description = " ".join(
                escape(self._translate(text))
                for text in (widget.field.description, source_note(name, value, source))
            )

    def updateActions(self):
        super().updateActions()
        self.actions["reset"].addClass("btn btn-secondary")

    def extractData(self, setErrors=True):
        data, errors = super().extractData(setErrors=setErrors)
        registry_values = get_registry_values()
        registry_values.update({
            name: value for name, value in data.items() if name in FIELDS
        })
        resolved = resolve_all(registry_values, read_env())
        for message in invariant_errors(resolved):
            view = getMultiAdapter(
                (Invalid(message), self.request, None, None, self, self.getContent()),
                IErrorViewSnippet,
            )
            view.update()
            errors += (view,)
        if setErrors:
            self.widgets.errors = errors
        return data, errors

    def applyChanges(self, data):
        # Locked fields are rendered in display mode and never extracted; this
        # also guards against crafted POSTs that switch the widget mode.
        for name in get_settings().locked:
            data.pop(name, None)
        return super().applyChanges(data)

    @button.buttonAndHandler(_("Reset to defaults"), name="reset")
    def handle_reset(self, action):
        locked = get_settings().locked
        for name in FIELDS:
            if name not in locked:
                set_registry_value(name, None)
        IStatusMessage(self.request).addStatusMessage(
            _("Settings reset. Environment variables or built-in defaults apply now."),
            "info",
        )
        self.request.response.redirect(self.request.getURL())


class QuotaControlPanel(ControlPanelFormWrapper):
    form = QuotaControlPanelForm
    index = ViewPageTemplateFile("../browser/templates/controlpanel.pt")

    def usage(self):
        return get_usage_info(self.context)

    def can_rebuild(self):
        # The page itself requires ManageSettings, which is what the rebuild
        # view requires too.
        return True

    def settings(self):
        return get_settings()

    def lock_enabled(self):
        return read_env().lock

    def usage_summary(self):
        info = self.usage()
        settings = self.settings()
        return {
            "total": human_readable_size(info.total),
            "hard": human_readable_size(info.hard) if info.hard else None,
            "soft": human_readable_size(info.soft) if info.soft else None,
            "percent": info.percent,
            "width": min(info.percent or 0, 100),
            "level": info.level,
            "bar_class": LEVEL_BARS.get(info.level, "bg-success"),
            "policy": POLICY_TITLES.get(settings.policy, settings.policy),
        }

    def source_rows(self):
        settings = self.settings()
        fields = getFields(IQuotaSettings)
        return [
            {
                "name": name,
                "title": fields[name].title,
                "value": format_value(name, settings.values[name]),
                "source": settings.sources[name],
                "source_label": SOURCE_LABELS[settings.sources[name]],
                "badge_class": SOURCE_BADGES[settings.sources[name]],
                "variable": ENV_VARS[name],
            }
            for name in FIELDS
        ]

    def usage_view_url(self):
        if self.context.restrictedTraverse("@@quota-usage", None) is None:
            return None
        return f"{self.context.absolute_url()}/@@quota-usage"

    def rebuild_url(self):
        return f"{self.context.absolute_url()}/@@quota-rebuild"
