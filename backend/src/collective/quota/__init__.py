"""Init and utils."""

from zope.i18nmessageid import MessageFactory

import logging


__version__ = "1.0.0a1"

PACKAGE_NAME = "collective.quota"

_ = MessageFactory(PACKAGE_NAME)

logger = logging.getLogger(PACKAGE_NAME)


def initialize(context):
    """Zope 2 product initialization: make BlobSizeIndex addable."""
    from collective.quota.catalog.blob_size_index import BlobSizeIndex
    from collective.quota.catalog.blob_size_index import manage_addBlobSizeIndex
    from collective.quota.catalog.blob_size_index import manage_addBlobSizeIndexForm

    context.registerClass(
        BlobSizeIndex,
        permission="Add Pluggable Index",
        constructors=(manage_addBlobSizeIndexForm, manage_addBlobSizeIndex),
        visibility=None,
    )
