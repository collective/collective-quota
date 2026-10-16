"""Warning banner for editors when the site is near or over its quota."""

from collective.quota.browser.summary import ALERT_CLASSES
from collective.quota.browser.summary import level_message
from collective.quota.settings import get_settings
from collective.quota.usage import get_usage_info
from plone.app.layout.viewlets.common import ViewletBase


# These pages show the usage summary themselves.
SUMMARY_VIEWS = frozenset({"quota-usage", "quota-controlpanel"})


class QuotaWarningViewlet(ViewletBase):
    def update(self):
        super().update()
        self.info = get_usage_info(self.portal_state.portal())
        self.settings = get_settings()

    @property
    def available(self) -> bool:
        # The ZCML permission already hides the viewlet; this also covers a
        # site that maps View Disk Usage to Anonymous by mistake.
        if self.portal_state.anonymous():
            return False
        if getattr(self.view, "__name__", None) in SUMMARY_VIEWS:
            return False
        return self.info.level in ALERT_CLASSES

    @property
    def css_class(self) -> str:
        return ALERT_CLASSES[self.info.level]

    @property
    def message(self):
        return level_message(self.info, self.settings)

    @property
    def usage_url(self) -> str:
        return f"{self.portal_state.portal_url()}/@@quota-usage"

    def render(self):
        return self.index() if self.available else ""
