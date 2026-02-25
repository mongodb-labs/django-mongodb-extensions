"""Views for MQL panel."""

from django.http import HttpResponseBadRequest, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt

from debug_toolbar._compat import login_not_required
from debug_toolbar.decorators import render_with_toolbar_language, require_show_toolbar
from debug_toolbar.panels.sql.views import get_signed_data

from .forms import MQLExplainForm, MQLSelectForm
from .utils import format_mql_query


@csrf_exempt
@login_not_required
@require_show_toolbar
@render_with_toolbar_language
def mql_explain(request):
    verified_data = get_signed_data(request)
    if not verified_data:
        return HttpResponseBadRequest("Invalid signature")
    form = MQLExplainForm(verified_data)

    if form.is_valid():
        query = form.cleaned_data["query"]
        result, headers = form.explain()

        context = {
            "result": result,
            "mql": format_mql_query(query),  # Pretty-printed MQL operation string
            "duration": query["duration"],
            "headers": headers,
            "alias": query["alias"],
        }
        content = render_to_string("debug_toolbar/panels/mql_explain.html", context)
        return JsonResponse({"content": content})
    return HttpResponseBadRequest("Form errors")


@csrf_exempt
@login_not_required
@require_show_toolbar
@render_with_toolbar_language
def mql_select(request):
    verified_data = get_signed_data(request)
    if not verified_data:
        return HttpResponseBadRequest("Invalid signature")
    form = MQLSelectForm(verified_data)

    if form.is_valid():
        query = form.cleaned_data["query"]
        result, headers = form.select()

        context = {
            "result": result,
            "mql": format_mql_query(query),  # Pretty-printed MQL operation string
            "duration": query["duration"],
            "headers": headers,
            "alias": query["alias"],
        }
        content = render_to_string("debug_toolbar/panels/mql_select.html", context)
        return JsonResponse({"content": content})
    return HttpResponseBadRequest("Form errors")
