# coding: utf-8
from __future__ import unicode_literals

from .settings import BACKEND
from django.core.cache import cache as _cache, get_cache as _get_cache

__all__ = ['cache', 'get_cache']


def get_cache(backend=BACKEND):
    if not backend:
        return _cache
    return _get_cache(backend)


cache = get_cache()


