from collective.quota import logger
from collective.quota.guard import guard_suspended
from pathlib import Path
from plone import api
from plone.exportimport import importers
from Products.GenericSetup.tool import SetupTool


EXAMPLE_CONTENT_FOLDER = Path(__file__).parent / "examplecontent"


def create_example_content(portal_setup: SetupTool):
    """Import content available at the examplecontent folder.

    Runs with the commit guard suspended so the sample files go in even when
    the site is already over its hard limit.
    """
    portal = api.portal.get()
    importer = importers.get_importer(portal)
    with guard_suspended():
        for line in importer.import_site(EXAMPLE_CONTENT_FOLDER):
            logger.info(line)
