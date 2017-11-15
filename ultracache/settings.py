# coding: utf-8
from __future__ import unicode_literals

from django.conf import settings

# The metadata itself can"t be allowed to grow endlessly. This value is the
# maximum size in bytes of a metadata list. If your caching backend supports
# compression set a larger value.
from .compat import importer

DEFAULT_SETTINGS = {
    "max-registry-value-size": 25000,
    "invalidate": True,
    "backend": None,
    "timeout": 300,
}

SETTINGS = dict(DEFAULT_SETTINGS)
SETTINGS.update(getattr(settings, 'ULTRACACHE', {}))

BACKEND = SETTINGS.get('backend')

MAX_SIZE = SETTINGS["max-registry-value-size"]
invalidate = SETTINGS["invalidate"]

CACHE_TIMEOUT = SETTINGS["timeout"]

try:
    purger = importer(SETTINGS["purge"]["method"])
except (AttributeError, KeyError):
    purger = None
