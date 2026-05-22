from django.urls import path

from dispatch import views


urlpatterns = [
    path("", views.home, name="home"),
    path("reports/weekly/", views.weekly_report, name="weekly_report"),
]
