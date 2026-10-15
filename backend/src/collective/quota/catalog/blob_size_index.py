"""``BlobSizeIndex``: a FieldIndex that also keeps the sum of its values."""

from BTrees.Length import Length
from collective.quota import guard
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex


class BlobSizeIndex(FieldIndex):
    """FieldIndex that also keeps the sum of all indexed values."""

    meta_type = "BlobSizeIndex"
    _total = None

    def clear(self):
        super().clear()
        self._total = Length(0)

    def _stored(self, documentId) -> int:
        value = self._unindex.get(documentId, 0)
        # bool is an int subclass but never a size.
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return 0

    def _apply_delta(self, delta: int) -> None:
        if delta:
            self._ensure_total().change(delta)
            guard.note_index_change(self, delta)

    def _index_object(self, documentId, obj, threshold=None, attr=""):
        # Compare stored values instead of trusting the return status: the base
        # class removes an entry but returns 0 when the datum becomes None.
        old = self._stored(documentId)
        changed = super()._index_object(documentId, obj, threshold, attr)
        self._apply_delta(self._stored(documentId) - old)
        return changed

    def unindex_object(self, documentId):
        old = self._stored(documentId)
        super().unindex_object(documentId)
        self._apply_delta(-old)

    def _ensure_total(self) -> Length:
        if self._total is None:
            self.rebuild_total()
        return self._total

    def total(self) -> int:
        """Sum of all indexed sizes, in bytes. O(1)."""
        return self._ensure_total()()

    def rebuild_total(self) -> int:
        """Recompute the total from the stored values."""
        self._total = Length(sum(self._stored(rid) for rid in self._unindex))
        return self._total()


manage_addBlobSizeIndexForm = PageTemplateFile(
    "templates/add_blob_size_index.pt",
    globals(),
    __name__="manage_addBlobSizeIndexForm",
)


def manage_addBlobSizeIndex(
    self,
    id,  # noqa: A002 (ZMI constructor signature)
    extra=None,
    REQUEST=None,
    RESPONSE=None,
    URL3=None,
):
    """Add a BlobSizeIndex (ZMI)."""
    return self.manage_addIndex(
        id,
        "BlobSizeIndex",
        extra=extra,
        REQUEST=REQUEST,
        RESPONSE=RESPONSE,
        URL1=URL3,
    )
