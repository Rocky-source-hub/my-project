from django.db import models
from django.conf import settings
from django.utils import timezone


class Officer(models.Model):
    """A LOOB user profile. The Administrator is a Django superuser and has no Officer profile."""

    class Role(models.TextChoices):
        ADMINISTRATOR = 'administrator' , 'Administrator'
        SCC = 'scc', 'SCC'
        SUPERVISOR = 'supervisor', 'Supervisor'
        SECTION_LEADER = 'section_leader', 'Section Leader'
        OFFICER = 'officer', 'Officer'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    full_name = models.CharField(max_length=150)
    badge_number = models.CharField(max_length=30, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OFFICER)
    active = models.BooleanField(default=True)

    # Track whether the user needs to set their own private password on first login
    must_change_password = models.BooleanField(default=True)

    # ---- Rights. Blank ("Unknown") = use the default for the role. Yes/No = Administrator override.
    add_occurrence_override = models.BooleanField(
        'Can add occurrences', null=True, blank=True,
        help_text='Leave as "Unknown" to use the role default '
                  '(SCC: no, Supervisor / Section Leader / Officer: yes).')
    add_followup_override = models.BooleanField(
        'Can add follow-ups', null=True, blank=True,
        help_text='Leave as "Unknown" to use the role default '
                  '(SCC: no, Supervisor / Section Leader / Officer: yes).')

    def __str__(self):
        return f'{self.full_name} - {self.badge_number}'

    # ---- rights helpers
    @property
    def is_scc(self):
        return self.role == self.Role.SCC

    def _role_default(self):
        # SCC is a view-only, real-time role until the Administrator grants more.
        return self.role not in (self.Role.SCC, self.Role.ADMINISTRATOR)

    @property
    def can_add_occurrence(self):
        if not self.active:
            return False
        if self.add_occurrence_override is not None:
            return self.add_occurrence_override
        return self._role_default()

    @property
    def can_add_followup(self):
        if not self.active:
            return False
        if self.add_followup_override is not None:
            return self.add_followup_override
        return self._role_default()


class Location(models.Model):
    name = models.CharField(max_length=200, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Occurrence(models.Model):
    officer = models.ForeignKey(Officer, on_delete=models.PROTECT)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    details = models.TextField()
    event_time = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f'LOOB-{self.pk:06d}' if self.pk is not None else 'New occurrence'


class FollowUp(models.Model):
    occurrence = models.ForeignKey(Occurrence, on_delete=models.PROTECT, related_name='followups')
    author = models.ForeignKey(Officer, on_delete=models.PROTECT)
    details = models.TextField()
    submitted_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f'Follow-up for {self.occurrence_id}'


class AuditLog(models.Model):
    occurrence = models.ForeignKey(Occurrence, on_delete=models.PROTECT, related_name='audit_logs')
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    previous_details = models.TextField()
    revised_details = models.TextField()
    reason = models.TextField()
    edited_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f'Amendment for {self.occurrence_id}'
