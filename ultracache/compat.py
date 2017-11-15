# coding: utf-8
from __future__ import unicode_literals

try:
    from django.utils.module_loading import import_string as importer
except ImportError:
    from django.utils.module_loading import import_by_path as importer
