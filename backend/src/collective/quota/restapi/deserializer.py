"""Hook C: refuse new items created through plone.restapi under ``block_all``."""

from collective.quota.guard import is_suspended
from collective.quota.guard import record_approved_add
from collective.quota.interfaces import IQuotaRestapiLayer
from collective.quota.policy import evaluate_add
from collective.quota.settings import get_settings
from collective.quota.usage import get_total_usage
from plone.dexterity.interfaces import IDexterityContent
from plone.restapi.deserializer.dxcontent import DeserializeFromJson
from plone.restapi.interfaces import IDeserializeFromJson
from zExceptions import BadRequest
from zope.component import adapter
from zope.i18n import translate
from zope.interface import implementer


@implementer(IDeserializeFromJson)
@adapter(IDexterityContent, IQuotaRestapiLayer)
class QuotaAwareDeserializer(DeserializeFromJson):
    """plone.restapi registers one deserializer for all Dexterity content
    (items and containers), so one override covers both."""

    def __call__(
        self, validate_all=False, data=None, create=False, mask_validation_errors=True
    ):
        # Imports (plone.exportimport) deserialize through here too; trusted
        # code inside guard_suspended() is not checked.
        if create and not is_suspended():
            decision = evaluate_add(get_total_usage(), get_settings())
            if not decision.allowed:
                raise BadRequest(translate(decision.message, context=self.request))
            record_approved_add()
        return super().__call__(
            validate_all=validate_all,
            data=data,
            create=create,
            mask_validation_errors=mask_validation_errors,
        )
