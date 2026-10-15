"""Hook B: refuse new items in Classic add forms under ``block_all``."""

from collective.quota.guard import record_approved_add
from collective.quota.interfaces import IBrowserLayer
from collective.quota.policy import evaluate_add
from collective.quota.settings import get_settings
from collective.quota.usage import get_total_usage
from z3c.form.interfaces import IAddForm
from z3c.form.validator import InvariantsValidator
from zope.annotation.interfaces import IAnnotations
from zope.component import adapter
from zope.interface import Interface
from zope.interface import Invalid
from zope.interface.interfaces import IInterface


CHECKED_KEY = "collective.quota.addform_checked"


@adapter(Interface, IBrowserLayer, IAddForm, IInterface, Interface)
class QuotaAddFormValidator(InvariantsValidator):
    def validate(self, data):
        errors = super().validate(data)
        # z3c.form calls manager validators once per schema in the form.
        checked = IAnnotations(self.request).setdefault(CHECKED_KEY, set())
        if id(self.view) in checked:
            return errors
        checked.add(id(self.view))
        decision = evaluate_add(get_total_usage(), get_settings())
        if not decision.allowed:
            return (*errors, Invalid(decision.message))
        record_approved_add()
        return errors
