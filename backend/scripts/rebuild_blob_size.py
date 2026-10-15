"""Rebuild collective.quota usage data on a (very large) site.

Usage:
    .venv/bin/zconsole run instance/etc/zope.conf scripts/rebuild_blob_size.py [site-id]

Re-catalogs every item for the ``blob_size`` index and metadata column,
committing every 1000 items, then recomputes the site total.
"""

from collective.quota.usage import rebuild_usage
from zope.component.hooks import setSite

import logging
import sys
import transaction


COMMIT_EVERY = 1000

logger = logging.getLogger("collective.quota")


def main(app, site_id="Plone") -> int:
    site = app.get(site_id)
    if site is None:
        logger.error("Site %r not found", site_id)
        return 1
    setSite(site)
    count = rebuild_usage(site, update_metadata=True, commit_every=COMMIT_EVERY)
    transaction.commit()
    logger.info("Rebuilt usage data for %d items on %r", count, site_id)
    return 0


if __name__ == "__main__" and "app" in globals():
    logging.basicConfig(level=logging.INFO)
    last = sys.argv[-1]
    sys.exit(main(app, "Plone" if last.endswith(".py") else last))  # noqa: F821
