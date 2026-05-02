from django.urls import path

from birthboard import (
    views,
)
from birthboard.api_yqpoint import check_yqpoint

urlpatterns = [
    path("", views.birthboard, name="birthboard"),
    path("confirm/", views.birthboard_confirm, name="birthboard_confirm"),
    path("approve/", views.birthboard_approve, name="birthboard_approve"),
] + [
    path("check_yqpoint/", check_yqpoint, name="check_yqpoint"),
    path("api/check_yqpoint/", check_yqpoint, name="check_yqpoint_api"),
]
