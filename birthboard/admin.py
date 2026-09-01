from django.contrib import admin
from birthboard.models import (
    BirthboardApprover,
    BirthboardContract,
    BirthboardSecondApprover,
)

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


@admin.register(BirthboardContract)
class BirthboardContractAdmin(admin.ModelAdmin):
    list_display = ("user", "signed", "signed_at", "restricted_until")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    list_filter = ("signed",)
    autocomplete_fields = ["user"]
    actions = ["clear_restriction"]

    @admin.action(description="解除限制参与")
    def clear_restriction(self, request, queryset):
        """批量清除所选用户的 restricted_until，随时中止生效中的限制。"""
        updated = queryset.update(restricted_until=None)
        self.message_user(request, f"已解除 {updated} 名用户的限制参与。")
