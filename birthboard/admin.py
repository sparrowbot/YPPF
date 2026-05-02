from django.contrib import admin
from birthboard.models import BirthboardApprover, BirthboardSecondApprover

@admin.register(BirthboardApprover)
class BirthboardApproverAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active", "created_at", "note")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    list_filter = ("is_active",)
    autocomplete_fields = ["user"]

@admin.register(BirthboardSecondApprover)
class BirthboardSecondApproverAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active", "created_at", "note")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    list_filter = ("is_active",)
    autocomplete_fields = ["user"]
