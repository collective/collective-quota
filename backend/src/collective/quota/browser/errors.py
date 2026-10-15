"""Error page for transactions aborted by the commit guard (hook D).

Plone's generic error page hides the exception message from non-managers;
this one shows the quota message to everybody.
"""

from plone.rest.errors import ErrorHandling
from plone.rest.interfaces import IAPIRequest
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

import json


class QuotaCommitAbortedView(BrowserView):
    template = ViewPageTemplateFile("templates/quota_error.pt")

    def __call__(self):
        exception = self.context
        if IAPIRequest.providedBy(self.request):
            return ErrorHandling(exception, self.request)()
        message = str(exception)
        self.request.response.setStatus(400)
        if "text/html" not in self.request.getHeader("Accept", ""):
            self.request.response.setHeader("Content-Type", "application/json")
            return json.dumps({
                "error_type": type(exception).__name__,
                "message": message,
            })
        # Render the page in the context where the error happened.
        self.context = self.__parent__
        self.request.set("disable_border", True)
        return self.template(message=message)
