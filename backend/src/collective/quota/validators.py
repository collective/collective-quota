"""Hook A: quota check for every upload into a ``plone.namedfile`` field.

Runs inside ``NamedField.validate()``, which z3c.form (Classic add/edit forms)
and plone.restapi (POST/PATCH, base64, multipart, TUS) both call.
"""

from collective.quota.guard import record_approved_bytes
from collective.quota.indexers.blob_size import get_stored_value
from collective.quota.policy import evaluate_upload
from collective.quota.policy import QuotaExceeded
from collective.quota.settings import get_settings
from collective.quota.usage import get_index
from collective.quota.usage import get_total_usage
from plone.namedfile.interfaces import INamedField
from plone.namedfile.interfaces import IPluggableFileFieldValidation
from plone.namedfile.interfaces import IPluggableImageFieldValidation
from z3c.form.interfaces import IAddForm
from zope.component import adapter
from zope.component.hooks import getSite
from zope.globalrequest import getRequest
from zope.interface import implementer
from zope.interface import Interface


def _in_add_form() -> bool:
    """True while a Classic add form is being processed.

    z3c.form binds the field to the *container* in add forms, so the value
    stored on the container must not be taken as this field's old value.
    """
    request = getRequest()
    published = request.get("PUBLISHED") if request is not None else None
    form = getattr(published, "form_instance", published)
    return IAddForm.providedBy(form)


def _old_value(field):
    context = getattr(field, "context", None)
    if context is None or _in_add_form():
        return None
    if field.interface is None:
        return getattr(context, field.__name__, None)
    return get_stored_value(context, field.interface, field.__name__)


@implementer(IPluggableFileFieldValidation, IPluggableImageFieldValidation)
@adapter(INamedField, Interface)
class QuotaUploadValidator:
    def __init__(self, field, value):
        self.field = field
        self.value = value

    def __call__(self):
        value = self.value
        if value is None or not hasattr(value, "getSize"):
            return
        old_value = _old_value(self.field)
        if old_value is value:
            return  # unchanged: "keep existing file" or a re-sent representation
        settings = get_settings()
        if settings.hard_bytes <= 0:
            return
        site = getSite()
        if site is None or get_index(site) is None:
            return
        old_size = int(old_value.getSize() or 0) if old_value is not None else 0
        new_size = int(value.getSize() or 0)
        decision = evaluate_upload(get_total_usage(site), old_size, new_size, settings)
        if not decision.allowed:
            raise QuotaExceeded(decision)
        if new_size > old_size:
            record_approved_bytes(new_size - old_size)
