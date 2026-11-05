from django.contrib import admin
from .models import Officer, Location, Occurrence, FollowUp, AuditLog

# Only the Administrator (superuser) may enter the Administrator area.
# Other users who happen to be 'staff' are refused.
admin.site.has_permission = lambda request: (
    request.user.is_active and request.user.is_superuser
)

admin.site.site_header = 'LOOB Administrator'
admin.site.site_title = 'LOOB Administrator'
admin.site.index_title = 'Administrator'


@admin.register(Officer)
class OfficerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'badge_number', 'role', 'active',
                    'can_add_occurrences', 'can_add_followups', 'must_change_password')
    search_fields = ('full_name', 'badge_number')
    list_filter = ('role', 'active', 'must_change_password')
    fieldsets = (
        ('Account', {'fields': ('user', 'full_name', 'badge_number', 'active', 'must_change_password')}),
        ('Role and rights', {
            'fields': ('role', 'add_occurrence_override', 'add_followup_override'),
            'description': 'SCC users can only view records in real time. Supervisors, Section Leaders and '
                           'Officers can add occurrences and follow-ups. Use the two rights below to grant '
                           'or remove a right for one person.',
        }),
    )

    @admin.display(boolean=True, description='Add occurrences')
    def can_add_occurrences(self, obj):
        return obj.can_add_occurrence

    @admin.display(boolean=True, description='Add follow-ups')
    def can_add_followups(self, obj):
        return obj.can_add_followup

    def has_delete_permission(self, request, obj=None):
        return False  # Deactivate instead; preserve personnel history.


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'active')
    search_fields = ('name',)

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyRecordsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Occurrence)
class OccurrenceAdmin(ReadOnlyRecordsAdmin):
    list_display = ('id', 'officer', 'location', 'submitted_at')
    search_fields = ('details', 'officer__full_name', 'officer__badge_number', 'location__name')


@admin.register(FollowUp)
class FollowUpAdmin(ReadOnlyRecordsAdmin):
    list_display = ('occurrence', 'author', 'submitted_at')


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyRecordsAdmin):
    list_display = ('occurrence', 'edited_by', 'edited_at')
