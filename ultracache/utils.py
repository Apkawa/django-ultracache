import sys
import hashlib
from django.conf import settings
from django.core.cache import cache
from django.contrib.sites.models import Site
from django.http import HttpResponse

from ultracache.settings import MAX_SIZE

try:
    from django.contrib.sites.shortcuts import get_current_site
except ImportError:
    from django.contrib.sites.models import get_current_site


def reduce_list_size(li):
    """Return two lists
        - the last N items of li whose total size is less than MAX_SIZE
        - the rest of the original list li
    """
    size = sys.getsizeof(li)
    keep = li
    toss = []
    n = len(li)
    decrement_by = max(n / 10, 10)
    while (size >= MAX_SIZE) and (n > 0):
        n -= decrement_by
        toss = li[:-n]
        keep = li[-n:]
        size = sys.getsizeof(keep)
    return keep, toss


def cache_meta(request, cache_key, start_index=0):
    """Inspect request for objects in _ultracache and set appropriate entries
    in Django's cache."""

    path = request.get_full_path()

    # Lists needed for cache.get_many
    to_set_get_keys = []
    to_set_paths_get_keys = []
    to_set_content_types_get_keys = []
    to_set_content_types_paths_get_keys = []

    # Dictionaries needed for cache.set_many
    to_set = {}
    to_set_paths = {}
    to_set_content_types = {}
    to_set_content_types_paths = {}

    to_delete = []
    to_set_objects = []

    for ctid, obj_pk in request._ultracache[start_index:]:
        # The object appears in these cache entries. If the object is modified
        # then these cache entries are deleted.
        key = "ucache-%s-%s" % (ctid, obj_pk)
        if key not in to_set_get_keys:
            to_set_get_keys.append(key)

        # The object appears in these paths. If the object is modified then any
        # caches that are read from when browsing to this path are cleared.
        key = "ucache-pth-%s-%s" % (ctid, obj_pk)
        if key not in to_set_paths_get_keys:
            to_set_paths_get_keys.append(key)

        # The content type appears in these cache entries. If an object of this
        # content type is created then these cache entries are cleared.
        key = "ucache-ct-%s" % ctid
        if key not in to_set_content_types_get_keys:
            to_set_content_types_get_keys.append(key)

        # The content type appears in these paths. If an object of this content
        # type is created then any caches that are read from when browsing to
        # this path are cleared.
        key = "ucache-ct-pth-%s" % ctid
        if key not in to_set_content_types_paths_get_keys:
            to_set_content_types_paths_get_keys.append(key)

        # A list of objects that contribute to a cache entry
        tu = (ctid, obj_pk)
        if tu not in to_set_objects:
            to_set_objects.append(tu)

    # todo: rewrite to handle absence of get_many
    di = cache.get_many(to_set_get_keys)
    for key in to_set_get_keys:
        v = di.get(key, None)
        keep = []
        if v is not None:
            keep, toss = reduce_list_size(v)
            if toss:
                to_set[key] = keep
                to_delete.extend(toss)
        if cache_key not in keep:
            if key not in to_set:
                to_set[key] = keep
            to_set[key] = to_set[key] + [cache_key]
    if to_set == di:
        to_set = {}

    di = cache.get_many(to_set_paths_get_keys)
    for key in to_set_paths_get_keys:
        v = di.get(key, None)
        keep = []
        if v is not None:
            keep, toss = reduce_list_size(v)
            if toss:
                to_set_paths[key] = keep
        if path not in keep:
            if key not in to_set_paths:
                to_set_paths[key] = keep
            to_set_paths[key] = to_set_paths[key] + [path]
    if to_set_paths == di:
        to_set_paths = {}

    di = cache.get_many(to_set_content_types_get_keys)
    for key in to_set_content_types_get_keys:
        v = di.get(key, None)
        keep = []
        if v is not None:
            keep, toss = reduce_list_size(v)
            if toss:
                to_set_content_types[key] = keep
                to_delete.extend(toss)
        if cache_key not in keep:
            if key not in to_set_content_types:
                to_set_content_types[key] = keep
            to_set_content_types[key] = to_set_content_types[key] + [cache_key]
    if to_set_content_types == di:
        to_set_content_types = {}

    di = cache.get_many(to_set_content_types_paths_get_keys)
    for key in to_set_content_types_paths_get_keys:
        v = di.get(key, None)
        keep = []
        if v is not None:
            keep, toss = reduce_list_size(v)
            if toss:
                to_set_content_types_paths[key] = keep
        if path not in keep:
            if key not in to_set_content_types_paths:
                to_set_content_types_paths[key] = keep
            to_set_content_types_paths[key] = to_set_content_types_paths[key] + [path]
    if to_set_content_types_paths == di:
        to_set_content_types_paths = {}

    # Deletion must happen first because set may set some of these keys
    if to_delete:
        try:
            cache.delete_many(to_delete)
        except NotImplementedError:
            for k in to_delete:
                cache.delete(k)

    # Do one set_many
    di = {}
    di.update(to_set)
    del to_set
    di.update(to_set_paths)
    del to_set_paths
    di.update(to_set_content_types)
    del to_set_content_types
    di.update(to_set_content_types_paths)
    del to_set_content_types_paths

    if to_set_objects:
        di[cache_key + "-objs"] = to_set_objects

    if di:
        try:
            cache.set_many(di, 86400)
        except NotImplementedError:
            for k, v in di.items():
                cache.set(k, v, 86400)


def get_current_site_pk(request):
    """Seemingly pointless function is so calling code doesn't have to worry
    about the import issues between Django 1.6 and later."""
    return get_current_site(request).pk


def get_cache_context(request, view_or_request, view_func, params, args, kwargs):
    # Compute a cache key
    li = [str(view_or_request.__class__), view_func.__name__]

    # request.get_full_path is implicitly added it no other request
    # path is provided. get_full_path includes the querystring and is
    # the more conservative approach but makes it trivially easy for a
    # request to bust through the cache.
    if not set(params).intersection({
        "request.get_full_path()", "request.path", "request.path_info"
    }):
        li.append(request.get_full_path())

    if "django.contrib.sites" in settings.INSTALLED_APPS:
        li.append(get_current_site_pk(request))

    li.extend(args)

    # Pre-sort kwargs
    keys = kwargs.keys()
    keys.sort()
    for key in keys:
        li.append("%s,%s" % (key, kwargs[key]))

    # Extend cache key with custom variables
    for param in params:
        if callable(param):
            param = param()

        li.append(param)
    return li


def build_cache_key(context, prefix="ucache-get-"):
    hashed = hashlib.md5(":".join([str(l) for l in context])).hexdigest()
    cache_key = "%s%s" % (prefix, hashed)
    return cache_key


def serialize_response(response):
    content = getattr(response, "rendered_content", None) \
              or getattr(response, "content", None)

    if content is not None:
        headers = getattr(response, "_headers", {})
        return {"content": content, "headers": headers}


def restore_response(serialized_response):
    response = HttpResponse(serialized_response["content"])
    # Headers has a non-obvious format
    for k, v in serialized_response["headers"].items():
        response[v[0]] = v[1]

    return response
