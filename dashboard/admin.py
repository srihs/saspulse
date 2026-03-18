from django.contrib import admin
from django import forms
from .models import DashboardCache, SystemSettings


class SystemSettingsAdminForm(forms.ModelForm):
    """Custom form for SystemSettings with enhanced validation"""
    class Meta:
        model = SystemSettings
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        # Call the model's clean method for validation
        instance = self.instance
        instance.fy_start_month = cleaned_data.get('fy_start_month', instance.fy_start_month)
        instance.fy_start_day = cleaned_data.get('fy_start_day', instance.fy_start_day)
        instance.fy_end_month = cleaned_data.get('fy_end_month', instance.fy_end_month)
        instance.fy_end_day = cleaned_data.get('fy_end_day', instance.fy_end_day)
        instance.clean()
        return cleaned_data


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    form = SystemSettingsAdminForm

    fieldsets = (
        ('Financial Year Configuration', {
            'fields': (
                ('fy_start_month', 'fy_start_day'),
                ('fy_end_month', 'fy_end_day'),
            ),
            'description': (
                '<strong>Configure the financial year period for your organization.</strong><br>'
                'The financial year must span across a calendar year boundary.<br><br>'
                '<strong>Examples:</strong><br>'
                '• April 1 to March 31 (NZ/AU/UK/India): Start Month=4, Start Day=1, End Month=3, End Day=31<br>'
                '• July 1 to June 30 (Old NZ system): Start Month=7, Start Day=1, End Month=6, End Day=30<br>'
                '• October 1 to September 30 (USA Federal): Start Month=10, Start Day=1, End Month=9, End Day=30<br><br>'
                '<em>Note: The start date must come after the end date in calendar terms (e.g., April > March, July > June).</em>'
            ),
        }),
        ('Metadata', {
            'fields': ('updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ['created_at', 'updated_at']
    list_display = ['__str__', 'fy_display', 'updated_at', 'updated_by']

    def fy_display(self, obj):
        """Display financial year in readable format"""
        months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        start = f"{months[obj.fy_start_month]} {obj.fy_start_day}"
        end = f"{months[obj.fy_end_month]} {obj.fy_end_day}"
        return f"{start} to {end}"
    fy_display.short_description = 'Financial Year Period'

    def has_add_permission(self, request):
        """Only allow one settings record - disable add if exists"""
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of settings"""
        return False

    def save_model(self, request, obj, form, change):
        """Automatically set updated_by to current user"""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DashboardCache)
class DashboardCacheAdmin(admin.ModelAdmin):
    list_display = ['cache_key', 'created_at', 'updated_at', 'expires_at']
    search_fields = ['cache_key']
    readonly_fields = ['created_at', 'updated_at']
