from django.contrib import admin

from .models import CrossPostAttempt


@admin.register(CrossPostAttempt)
class CrossPostAttemptAdmin(admin.ModelAdmin):
    list_display = ['id', 'post_id', 'content_type', 'network', 'status', 'external_id', 'created_at']
    list_filter = ['network', 'status', 'content_type', 'created_at']
    search_fields = ['post_id', 'external_id', 'error']
    readonly_fields = ['created_at']
    ordering = ['-created_at']