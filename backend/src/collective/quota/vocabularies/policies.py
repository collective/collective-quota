"""Vocabulary of over-limit policies."""

from collective.quota import _
from collective.quota.policy import ALLOW
from collective.quota.policy import BLOCK_ALL
from collective.quota.policy import BLOCK_FILES
from collective.quota.policy import LIMIT_FILE_SIZE
from zope.interface import provider
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


POLICY_TITLES = {
    BLOCK_ALL: _("Block new items and any upload that adds bytes"),
    BLOCK_FILES: _("Allow new items, block uploads that add bytes"),
    LIMIT_FILE_SIZE: _("Allow uploads up to a maximum file size"),
    ALLOW: _("Allow everything, only show warnings"),
}


@provider(IVocabularyFactory)
def over_limit_policies(context=None):
    return SimpleVocabulary([
        SimpleTerm(value=token, token=token, title=title)
        for token, title in POLICY_TITLES.items()
    ])
