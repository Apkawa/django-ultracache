from hashlib import md5
import types
from functools import wraps

from django.http import HttpResponse
from django.utils.decorators import available_attrs
from django.views.generic.base import TemplateResponseMixin
from django.conf import settings

from . import _thread_locals
from .utils import cache_meta, get_current_site_pk, get_cache_context, build_cache_key, serialize_response, \
    restore_response
from .cache import get_cache
from .settings import CACHE_TIMEOUT


def allow_purge(view, request, *args, **kwargs):
    return request.META.get('HTTP_X_CACHE_PURGE')


def is_messages(request):
    try:
        return len(request._messages) > 0
    except (AttributeError, TypeError):
        pass
    return False


def cached_get(*params, **kwargs):
    timeout = kwargs.get('timeout') or CACHE_TIMEOUT
    backend = kwargs.get('backend')
    cache = get_cache(backend)

    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(view_or_request, *args, **kwargs):

            # The type of the request gets muddled when using a function based
            # decorator. We must use a function based decorator so it can be
            # used in urls.py.
            request = getattr(view_or_request, "request", view_or_request)

            if not hasattr(_thread_locals, "ultracache_request"):
                setattr(_thread_locals, "ultracache_request", request)

            # If request not GET or HEAD never cache
            if request.method.lower() not in ("get", "head"):
                return view_func(view_or_request, *args, **kwargs)

            # If request contains messages never cache
            if is_messages(request):
                return view_func(view_or_request, *args, **kwargs)

            cache_context = get_cache_context(
                request=request,
                view_or_request=view_or_request,
                view_func=view_func,
                params=params,
                args=args,
                kwargs=kwargs
            )
            cache_key = build_cache_key(context=cache_context, prefix="ucache-get-")
            cached = cache.get(cache_key, None)
            if cached and allow_purge(view_func, request, *args, **kwargs):
                # cache.delete(cache_key)
                cached = None

            if cached is not None:
                response = restore_response(cached)
                return response

            # The get view as outermost caller may bluntly set _ultracache
            request._ultracache = []
            response = view_func(view_or_request, *args, **kwargs)
            data = serialize_response(response)
            if data is not None:
                cache.set(
                    cache_key,
                    data,
                    timeout
                )
                cache_meta(request, cache_key)

            return response

        return _wrapped_view

    return decorator
