from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.dexterity.fti import DexterityFTI
from plone.namedfile.field import NamedBlobFile
from plone.namedfile.field import NamedBlobImage
from plone.supermodel import model
from plone.testing import zope as zope_testing
from plone.testing.zope import WSGI_SERVER_FIXTURE
from zope import schema

import collective.quota


MULTI_BLOB_TYPE = "quota_multi"


class IMultiBlobSchema(model.Schema):
    """Test-only schema with several blob fields."""

    title = schema.TextLine(title="Title")
    attachment = NamedBlobFile(title="Attachment", required=False)
    picture = NamedBlobImage(title="Picture", required=False)
    second = NamedBlobFile(title="Second attachment", required=False)


class Layer(PloneSandboxLayer):
    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.exportimport
        import plone.restapi

        self.loadZCML(package=plone.exportimport)
        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=collective.quota)
        # Runs collective.quota.initialize (registers the BlobSizeIndex class).
        zope_testing.installProduct(app, "collective.quota")

    def tearDownZope(self, app):
        zope_testing.uninstallProduct(app, "collective.quota")

    def setUpPloneSite(self, portal):
        applyProfile(portal, "collective.quota:default")
        types_tool = portal.portal_types

        fti = DexterityFTI(MULTI_BLOB_TYPE)
        fti.title = "Quota multi blob"
        fti.klass = "plone.dexterity.content.Item"
        fti.schema = "collective.quota.testing.IMultiBlobSchema"
        fti.behaviors = ("plone.namefromtitle", "plone.basic")
        fti.global_allow = True
        fti.add_permission = "cmf.AddPortalContent"
        types_tool._setObject(MULTI_BLOB_TYPE, fti)

        # Lead image on Document, test layer only: blob field from a behavior.
        document = types_tool["Document"]
        document.behaviors = (*document.behaviors, "plone.leadimage")


FIXTURE = Layer()

INTEGRATION_TESTING = IntegrationTesting(
    bases=(FIXTURE,),
    name="Collective.QuotaLayer:IntegrationTesting",
)


FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(FIXTURE, WSGI_SERVER_FIXTURE),
    name="Collective.QuotaLayer:FunctionalTesting",
)


ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        WSGI_SERVER_FIXTURE,
    ),
    name="Collective.QuotaLayer:AcceptanceTesting",
)
