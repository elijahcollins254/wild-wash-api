import re

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import URLPattern, URLResolver, get_resolver


def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({'status': 'ok'})


def _route_parts(pattern) -> tuple[str, str]:
    route = getattr(pattern, '_route', None)
    if route is not None:
        display_path = route

        def replace_converter(match):
            converter, name = match.groups()
            if converter == 'drf_format_suffix':
                return ''
            if converter == 'int':
                return '1'
            if converter == 'uuid':
                return '00000000-0000-0000-0000-000000000000'
            return 'json' if name == 'format' else 'example'

        link_path = re.sub(r'<(?:(\w+):)?(\w+)>', replace_converter, route)
        return display_path, link_path

    route = pattern.regex.pattern.lstrip('^').rstrip('$').replace(r'\/', '/')
    route = route.replace('/?', '/')

    def replace_group(match):
        name, expression = match.groups()
        if name == 'format':
            return '<{}>'.format(name), 'json'
        sample = '1' if re.search(r'\d|\[0-9', expression) else 'example'
        return '<{}>'.format(name), sample

    link_path = route

    def group_for_display(match):
        nonlocal link_path
        display, sample = replace_group(match)
        link_path = link_path.replace(match.group(0), sample, 1)
        return display

    display_path = re.sub(r'\(\?P<([^>]+)>([^)]*)\)', group_for_display, route)
    display_path = display_path.replace(r'\.', '.')
    link_path = link_path.replace(r'\.', '.')
    return display_path, link_path


def _collect_endpoint_links(patterns, prefix=''):
    endpoints = []
    for pattern in patterns:
        route, link_route = _route_parts(pattern.pattern)
        if isinstance(pattern, URLResolver):
            endpoints.extend(
                _collect_endpoint_links(pattern.url_patterns, prefix + route)
            )
        elif isinstance(pattern, URLPattern):
            display_path = prefix + route
            href = '/' + (prefix + link_route).lstrip('/')
            endpoints.append({
                'path': '/' + display_path.lstrip('/'),
                'href': href,
                'name': pattern.name or 'Endpoint',
            })
    return endpoints


def endpoint_index(request: HttpRequest) -> HttpResponse:
    endpoints = _collect_endpoint_links(get_resolver().url_patterns)
    return render(request, 'api/endpoint_index.html', {'endpoints': endpoints})
