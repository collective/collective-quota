"""``GET @quota-usage``: usage summary and the biggest items, as JSON."""

from collective.quota.listing import biggest_items
from collective.quota.listing import LIMITS
from collective.quota.listing import parse_limit
from collective.quota.settings import get_settings
from collective.quota.summary import level_message
from collective.quota.summary import policy_hint
from collective.quota.usage import get_usage_info
from collective.quota.utils import human_readable_size
from collective.quota.vocabularies.policies import POLICY_TITLES
from plone import api
from plone.restapi.serializer.converters import json_compatible
from plone.restapi.services import Service
from zope.i18n import translate


MANAGE_SETTINGS = "collective.quota: Manage Quota Settings"
VIEW_DISK_USAGE = "collective.quota: View Disk Usage"


def _human(size):
    return human_readable_size(size) if size else None


def _translate(message, request):
    return translate(message, context=request) if message is not None else None


def usage_payload(portal, request) -> dict:
    """Summary keys of ``@quota-usage``, shared with the ``quota`` expander."""
    info = get_usage_info(portal)
    settings = get_settings()
    can_manage = api.user.has_permission(MANAGE_SETTINGS, obj=portal)
    portal_url = portal.absolute_url()
    payload = {
        "@id": f"{portal_url}/@quota-usage",
        "total": info.total,
        "total_human": human_readable_size(info.total),
        "soft": info.soft,
        "soft_human": _human(info.soft),
        "hard": info.hard,
        "hard_human": _human(info.hard),
        "percent": info.percent,
        "level": info.level,
        "limits_configured": bool(info.soft or info.hard),
        "message": _translate(level_message(info, settings), request),
        "policy": settings.policy,
        "policy_title": _translate(
            POLICY_TITLES.get(settings.policy, settings.policy), request
        ),
        "policy_hint": _translate(
            policy_hint(settings) if info.hard else None, request
        ),
        "can_manage": can_manage,
    }
    if can_manage:
        payload["controlpanel"] = f"{portal_url}/@controlpanels/collective-quota"
    return payload


def item_payload(item) -> dict:
    return {
        "@id": item.url,
        "UID": item.uid,
        "title": item.title,
        "@type": item.portal_type,
        "type_title": item.type_title,
        "parent": {"@id": item.parent_url, "title": item.parent_title},
        "blob_size": item.size,
        "blob_size_human": human_readable_size(item.size),
        "modified": json_compatible(item.modified),
        "can_delete": item.can_delete,
    }


class QuotaUsageGet(Service):
    def reply(self):
        limit = parse_limit(self.request.form.get("limit"))
        result = usage_payload(self.context, self.request)
        result["limit"] = limit
        result["limits"] = list(LIMITS)
        result["items"] = [
            item_payload(item)
            for item in biggest_items(self.context, self.request, limit)
        ]
        return result
