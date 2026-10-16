"""REST control panel: ``@controlpanels/collective-quota``.

``data`` holds what the control panel stores (registry values, ``None`` when
unset), except locked fields, which show their environment value. Extra
top-level keys explain the effective configuration: ``effective`` (values in
use), ``sources`` and ``locked``. PATCH refuses to change locked fields and
checks the invariants on the effective values before writing anything.
"""

from collective.quota import _
from collective.quota.interfaces import IQuotaControlpanel
from collective.quota.interfaces import IQuotaRestapiLayer
from collective.quota.interfaces import IQuotaSettings
from collective.quota.settings import ENV_VARS
from collective.quota.settings import get_registry_values
from collective.quota.settings import get_settings
from collective.quota.settings import invariant_errors
from collective.quota.settings import read_env
from collective.quota.settings import REGISTRY_PREFIX
from collective.quota.settings import resolve_all
from plone.registry.interfaces import IRegistry
from plone.restapi.controlpanels import RegistryConfigletPanel
from plone.restapi.deserializer import json_body
from plone.restapi.deserializer.controlpanels import ControlpanelDeserializeFromJson
from plone.restapi.deserializer.controlpanels import FakeDXContext
from plone.restapi.interfaces import IDeserializeFromJson
from plone.restapi.interfaces import IFieldDeserializer
from plone.restapi.interfaces import IFieldSerializer
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.serializer.controlpanels import ControlpanelSerializeToJson
from zExceptions import BadRequest
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.i18n import translate
from zope.interface import implementer
from zope.interface import Interface
from zope.schema import getFields
from zope.schema.interfaces import ValidationError


@implementer(IQuotaControlpanel)
@adapter(Interface, IQuotaRestapiLayer)
class QuotaConfigletPanel(RegistryConfigletPanel):
    schema = IQuotaSettings
    schema_prefix = REGISTRY_PREFIX
    configlet_id = "collective-quota"
    configlet_category_id = "Products"
    title = _("Quota")


@implementer(IQuotaSettings)
class EffectiveValues(FakeDXContext):
    """Holds environment values so the DX field serializers can render them."""


@implementer(ISerializeToJson)
@adapter(IQuotaControlpanel)
class QuotaControlpanelSerializeToJson(ControlpanelSerializeToJson):
    def __call__(self):
        result = super().__call__()
        settings = get_settings()
        fields = getFields(self.schema)
        for name in settings.locked:
            # Serialize the environment value like any other field value.
            fake_context = EffectiveValues()
            setattr(fake_context, name, settings.values[name])
            serializer = getMultiAdapter(
                (fields[name], fake_context, self.controlpanel.request),
                IFieldSerializer,
            )
            result["data"][name] = serializer()
            result["schema"]["properties"][name]["readonly"] = True
        result["effective"] = dict(settings.values)
        result["sources"] = dict(settings.sources)
        result["locked"] = sorted(settings.locked)
        return result


@implementer(IDeserializeFromJson)
@adapter(IQuotaControlpanel)
class QuotaControlpanelDeserializeFromJson(ControlpanelDeserializeFromJson):
    def _raise(self, errors):
        for error in errors:
            error["message"] = translate(error["message"], context=self.request)
        raise BadRequest(errors)

    def _locked_errors(self, data, settings):
        """Sending a locked field's own value back is harmless (clients often
        send the whole form) and is ignored; any other value is refused."""
        return [
            {
                "message": _(
                    "Setting ${name} is locked by environment variable ${variable}",
                    mapping={"name": name, "variable": ENV_VARS[name]},
                ),
                "field": name,
                "error": "ValidationError",
            }
            for name in sorted(settings.locked)
            if name in data and data[name] != settings.values[name]
        ]

    def _deserialize(self, data, settings):
        """``(values, errors)`` for the editable fields present in ``data``."""
        values, errors = {}, []
        fake_context = FakeDXContext()
        for name, field in getFields(self.schema).items():
            if name not in data or name in settings.locked:
                continue
            deserializer = getMultiAdapter(
                (field, fake_context, self.request), IFieldDeserializer
            )
            try:
                value = deserializer(data[name])
                field.validate(value)
            except ValidationError as e:
                errors.append({"message": e.doc(), "field": name, "error": e})
            else:
                values[name] = value
        return values, errors

    def _invariant_errors(self, values):
        registry_values = get_registry_values()
        registry_values.update(values)
        resolved = resolve_all(registry_values, read_env())
        return [
            {"message": message, "error": "ValidationError"}
            for message in invariant_errors(resolved)
        ]

    def __call__(self, mask_validation_errors=True):
        data = json_body(self.request)
        settings = get_settings()
        locked_errors = self._locked_errors(data, settings)
        if locked_errors:
            self._raise(locked_errors)
        values, errors = self._deserialize(data, settings)
        if not errors:
            errors = self._invariant_errors(values)
        if errors:
            if mask_validation_errors:
                for error in errors:
                    error["error"] = "ValidationError"
            self._raise(errors)
        # Nothing is written until every check passed.
        proxy = getUtility(IRegistry).forInterface(
            self.schema, prefix=self.schema_prefix
        )
        for name, value in values.items():
            setattr(proxy, name, value)
