from datetime import datetime, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.db.models import Q, Count
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Officer, Location, Occurrence, FollowUp, AuditLog
from .forms import OccurrenceForm, FollowUpForm, AmendmentForm


# ---------------------------------------------------------------- roles & password protection
def is_manager(user):
    """The Administrator is the superuser in this prototype."""
    return user.is_authenticated and user.is_active and user.is_superuser


def get_officer(user):
    """Return the active Officer profile of this user, or None (e.g. the Administrator)."""
    if not user.is_authenticated:
        return None
    return Officer.objects.filter(user=user, active=True, user__is_active=True).first()


def force_password_change_check(view_func):
    """Decorator to redirect users to change password on first login."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            officer = get_officer(request.user)
            if officer and officer.must_change_password:
                messages.warning(request, "For security reasons, you must set a new password before continuing.")
                return redirect('force_password_change')
        return view_func(request, *args, **kwargs)
    return wrapper


def manager_required(view):
    """Only the Administrator may open this page. Everyone else gets 403."""
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_manager(request.user):
            return HttpResponseForbidden('This area is for the Administrator only.')
        return view(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------- password change view
class ForcedPasswordChangeView(PasswordChangeView):
    """View to allow a user to set a private password and clear the flag."""
    template_name = 'occurrences/password_change_form.html'
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        officer = get_officer(self.request.user)
        if officer:
            officer.must_change_password = False
            officer.save(update_fields=['must_change_password'])
        messages.success(self.request, "Your password has been updated successfully!")
        return response


# ---------------------------------------------------------------- dashboard
def _apply_search(records, params):
    keyword = params.get('q', '').strip()
    location = params.get('location', '').strip()
    date = params.get('date', '').strip()
    time = params.get('time', '').strip()
    if keyword:
        records = records.filter(
            Q(details__icontains=keyword) | Q(officer__full_name__icontains=keyword) |
            Q(officer__badge_number__icontains=keyword) | Q(location__name__icontains=keyword) |
            Q(followups__details__icontains=keyword) | Q(followups__author__full_name__icontains=keyword)
        ).distinct()
    if location:
        records = records.filter(location__name__icontains=location)
    if date:
        selected_date = parse_date(date)
        if selected_date:
            records = records.filter(submitted_at__date=selected_date)
    if time:
        try:
            selected_time = datetime.strptime(time, '%H:%M').time()
            records = records.filter(submitted_at__hour=selected_time.hour,
                                     submitted_at__minute=selected_time.minute)
        except ValueError:
            pass
    return records


@login_required
@force_password_change_check
def dashboard(request):
    manager = is_manager(request.user)
    officer = get_officer(request.user)
    is_scc = bool(officer and officer.is_scc)
    base = Occurrence.objects.select_related('officer', 'location').order_by('-submitted_at', '-pk')
    records = _apply_search(base, request.GET)

    today = timezone.localdate()
    context = {
        'records': records[:100],
        'is_manager': manager,
        'officer': officer,
        'is_scc': is_scc,
        'can_add': bool(officer and officer.can_add_occurrence),
        'locations': Location.objects.filter(active=True).order_by('name'),
        'searching': any(request.GET.get(k, '').strip() for k in ('q', 'location', 'date', 'time')),
    }

    if manager:
        week_start = today - timedelta(days=6)
        by_location = list(
            Occurrence.objects.values('location__name').annotate(n=Count('id')).order_by('-n')[:6]
        )
        top = by_location[0]['n'] if by_location else 1
        for row in by_location:
            row['pct'] = max(6, round(row['n'] * 100 / top))
        context['stats'] = {
            'total': Occurrence.objects.count(),
            'today': Occurrence.objects.filter(submitted_at__date=today).count(),
            'week': Occurrence.objects.filter(submitted_at__date__gte=week_start).count(),
            'officers': Officer.objects.filter(active=True).count(),
            'followups': FollowUp.objects.count(),
            'amendments': AuditLog.objects.count(),
        }
        context['by_location'] = by_location
    elif is_scc:
        context['stats'] = {
            'all_today': Occurrence.objects.filter(submitted_at__date=today).count(),
            'all_total': Occurrence.objects.count(),
        }
    elif officer:
        mine = Occurrence.objects.filter(officer=officer)
        context['stats'] = {
            'mine_today': mine.filter(submitted_at__date=today).count(),
            'mine_total': mine.count(),
        }
    return render(request, 'occurrences/dashboard.html', context)


# ---------------------------------------------------------------- entries
@login_required
@force_password_change_check
def new_entry(request):
    officer = get_officer(request.user)
    if officer is None:
        messages.error(request, 'Only registered, active users can make occurrence entries. '
                                'The Administrator can review and amend entries but cannot create them.')
        return redirect('dashboard')
    if not officer.can_add_occurrence:
        messages.error(request, 'Your account does not have the right to add occurrences. '
                                'Contact the Administrator.')
        return redirect('dashboard')
    form = OccurrenceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        entry.officer = officer
        entry.save()
        messages.success(request, 'Occurrence submitted successfully.')
        return redirect('occurrence_detail', pk=entry.pk)
    return render(request, 'occurrences/form.html', {'form': form, 'officer': officer})


@login_required
@force_password_change_check
def occurrence_detail(request, pk):
    record = get_object_or_404(Occurrence.objects.select_related('officer', 'location'), pk=pk)
    officer = get_officer(request.user)
    manager = is_manager(request.user)
    can_followup = bool(
        officer 
        and officer.can_add_followup
        and record.officer_id== officer .pk
        )
    form = FollowUpForm(request.POST or None)
    if request.method == 'POST':
        if not can_followup:
            return HttpResponseForbidden('You can only add follow-ups to your own entries.')
        if form.is_valid():
            followup = form.save(commit=False)
            followup.occurrence = record
            followup.author = officer
            followup.save()
            messages.success(request, 'Follow-up saved successfully.')
            return redirect('occurrence_detail', pk=pk)
    return render(request, 'occurrences/detail.html', {
        'record': record, 'form': form, 'is_manager': manager, 'can_followup': can_followup,
        'audit_logs': record.audit_logs.select_related('edited_by').order_by('-edited_at') if manager else None,
    })


@manager_required
def amend_occurrence(request, pk):
    record = get_object_or_404(Occurrence, pk=pk)
    form = AmendmentForm(request.POST or None, initial={'revised_details': record.details})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            locked = Occurrence.objects.select_for_update().get(pk=pk)
            previous = locked.details
            revised = form.cleaned_data['revised_details']
            AuditLog.objects.create(
                occurrence=locked, edited_by=request.user, previous_details=previous,
                revised_details=revised, reason=form.cleaned_data['reason'],
            )
            locked.details = revised
            locked.save(update_fields=['details'])
        messages.success(request, 'Amendment saved with audit history.')
        return redirect('occurrence_detail', pk=pk)
    return render(request, 'occurrences/amend.html', {'form': form, 'record': record})


# ---------------------------------------------------------------- administrator area
@manager_required
def officer_roster(request):
    officers = (Officer.objects.select_related('user')
                .annotate(entries=Count('occurrence', distinct=True))
                .order_by('-active', 'full_name'))
    return render(request, 'occurrences/roster.html', {'officers': officers, 'is_manager': True})
