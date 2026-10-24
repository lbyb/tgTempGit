"""User-facing exception types.

The CLI and the GUI both catch :class:`PupdfError` and show ``str(exc)``
directly, so messages raised anywhere in the core should be written for an
end user (Chinese is used in this project) and should never contain a
traceback.
"""

from __future__ import annotations


class PupdfError(Exception):
    """Base class for every expected, recoverable error."""


class UserInputError(PupdfError):
    """A page number, path or option supplied by the user is not valid."""


class DiscoveryError(PupdfError):
    """The single input PDF could not be determined."""


class PdfOperationError(PupdfError):
    """A PDF could not be opened, changed, or written safely."""


class EncryptedPdfError(PdfOperationError):
    """The PDF requires a password and therefore cannot be processed."""
