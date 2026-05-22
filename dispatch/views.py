from django.shortcuts import render
from django.views.decorators.cache import never_cache

from dispatch.models import DispatchResult
from dispatch.services.reporting import build_weekly_report


def home(request):
    return render(request, "dispatch/home.html")


@never_cache
def weekly_report(request):
    if not DispatchResult.objects.exists():
        return render(request, "dispatch/report_missing_data.html")

    report = build_weekly_report()
    return render(request, "dispatch/weekly_report.html", {"report": report})
