"""
Vanta: Ingestion Schemas (Layer 1 Validation) - Consolidated Re-export

Single source of truth is app/core/ingestion/schemas.py. This module is kept
only so legacy imports `from .schemas_fixed import ...` do not break.
"""
from .schemas import *  # noqa
from .schemas import (
    MediaType,
    PhotoMedia,
    VideoMedia,
    GenericAttachmentMedia,
    ApifyFacebookPost,
    ApifyFacebookPostClean,
    PostSummary,
)
