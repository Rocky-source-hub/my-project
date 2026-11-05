from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Officer, Location, Occurrence, FollowUp, AuditLog


class LOOBTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='00404538', password='StrongTestPassword!')
        self.officer = Officer.objects.create(user=self.user, full_name='Michael Rockson Kushigbor',
                                              badge_number='00404538', must_change_password=False)
        self.location = Location.objects.create(name='Site Main Gate')
        self.manager = User.objects.create_superuser(username='manager', email='manager@example.invalid',
                                                     password='StrongTestPassword!')

    def make_user(self, username, role, **extra):
        user = get_user_model().objects.create_user(username=username, password='StrongTestPassword!')
        officer = Officer.objects.create(user=user, full_name=f'Test {role}', badge_number=username,
                                         role=role, must_change_password=False, **extra)
        return user, officer

    def test_login_required(self):
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)

    def test_login_page_has_no_tagline(self):
        html = self.client.get(reverse('login')).content.decode()
        self.assertNotIn('recorded once and time-stamped', html)

    def test_officer_submission_uses_logged_in_identity(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('new_entry'), {'location': self.location.pk, 'event_time': '', 'details': 'Routine inspection.'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Occurrence.objects.get().officer, self.officer)

    def test_followup_does_not_change_original(self):
        record = Occurrence.objects.create(officer=self.officer, location=self.location, details='Original')
        self.client.force_login(self.user)
        self.client.post(reverse('occurrence_detail', args=[record.pk]), {'details': 'Additional information'})
        record.refresh_from_db()
        self.assertEqual(record.details, 'Original')
        self.assertEqual(FollowUp.objects.count(), 1)

    def test_only_administrator_can_amend(self):
        record = Occurrence.objects.create(officer=self.officer, location=self.location, details='Original')
        url = reverse('amend_occurrence', args=[record.pk])
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url, {'revised_details': 'Changed', 'reason': 'Correction'}).status_code, 403)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(url, {'revised_details': 'Changed', 'reason': 'Correction'}).status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.details, 'Changed')
        self.assertEqual(AuditLog.objects.get().previous_details, 'Original')

    # ---- role separation (Administrator area must be invisible and closed to everyone else)
    def test_officer_never_sees_admin_links(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertNotIn('/admin/', html)
        self.assertNotIn('Administrator', html)
        self.assertNotIn('Administrator amendments', html)

    def test_staff_officer_cannot_enter_admin(self):
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get('/admin/', follow=True)
        self.assertNotContains(response, 'Site administration')
        self.assertNotContains(response, 'Officers</a>')

    def test_officer_cannot_open_administrator_pages(self):
        record = Occurrence.objects.create(officer=self.officer, location=self.location, details='Original')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('officer_roster')).status_code, 403)
        self.assertEqual(self.client.get(reverse('amend_occurrence', args=[record.pk])).status_code, 403)
        detail = self.client.get(reverse('occurrence_detail', args=[record.pk])).content.decode()
        self.assertNotIn('amendment history', detail)

    def test_administrator_sees_admin_area_and_stats(self):
        self.client.force_login(self.manager)
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('Administrator', html)
        self.assertNotIn('Administration', html)
        self.assertIn('Administrator amendments', html)
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        self.assertEqual(self.client.get(reverse('officer_roster')).status_code, 200)

    def test_admin_pages_have_navigation_back(self):
        self.client.force_login(self.manager)
        html = self.client.get('/admin/').content.decode()
        self.assertIn(reverse('dashboard'), html)
        self.assertIn(reverse('officer_roster'), html)
        self.assertIn('Dashboard', html)
        self.assertIn('Officers', html)

    def test_administrator_without_profile_cannot_create_entries(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('new_entry'), {'location': self.location.pk, 'details': 'x'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Occurrence.objects.count(), 0)

    # ---- roles: SCC, Supervisor, Section Leader, Officer
    def test_scc_is_view_only_by_default(self):
        scc, _ = self.make_user('scc1', Officer.Role.SCC)
        record = Occurrence.objects.create(officer=self.officer, location=self.location, details='Original')
        self.client.force_login(scc)
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('Live Occurrence Monitor', html)
        self.assertNotIn('New Occurrence', html)
        self.assertEqual(self.client.get(reverse('occurrence_detail', args=[record.pk])).status_code, 200)
        # cannot add an occurrence
        r = self.client.post(reverse('new_entry'), {'location': self.location.pk, 'details': 'x'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Occurrence.objects.count(), 1)
        # cannot add a follow-up
        r = self.client.post(reverse('occurrence_detail', args=[record.pk]), {'details': 'x'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(FollowUp.objects.count(), 0)

    def test_scc_cannot_open_administrator_pages(self):
        scc, _ = self.make_user('scc1', Officer.Role.SCC)
        self.client.force_login(scc)
        self.assertEqual(self.client.get(reverse('officer_roster')).status_code, 403)

    def test_administrator_can_grant_scc_extra_rights(self):
        scc, officer = self.make_user('scc1', Officer.Role.SCC, add_followup_override=True)
        record = Occurrence.objects.create(officer=self.officer, location=self.location, details='Original')
        self.client.force_login(scc)
        r = self.client.post(reverse('occurrence_detail', args=[record.pk]), {'details': 'Seen on CCTV'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(FollowUp.objects.count(), 1)
        # still cannot add occurrences (not granted)
        self.client.post(reverse('new_entry'), {'location': self.location.pk, 'details': 'x'})
        self.assertEqual(Occurrence.objects.count(), 1)

    def test_supervisor_section_leader_officer_can_add_occurrence_and_followup(self):
        for i, role in enumerate([Officer.Role.SUPERVISOR, Officer.Role.SECTION_LEADER, Officer.Role.OFFICER]):
            user, officer = self.make_user(f'u{i}', role)
            self.client.force_login(user)
            r = self.client.post(reverse('new_entry'), {'location': self.location.pk, 'event_time': '', 'details': f'Entry {role}'})
            self.assertEqual(r.status_code, 302)
            record = Occurrence.objects.get(details=f'Entry {role}')
            self.assertEqual(record.officer, officer)
            r = self.client.post(reverse('occurrence_detail', args=[record.pk]), {'details': 'More'})
            self.assertEqual(r.status_code, 302)
        self.assertEqual(FollowUp.objects.count(), 3)

    def test_administrator_can_remove_a_right(self):
        user, _ = self.make_user('sup1', Officer.Role.SUPERVISOR, add_occurrence_override=False)
        self.client.force_login(user)
        self.client.post(reverse('new_entry'), {'location': self.location.pk, 'details': 'x'})
        self.assertEqual(Occurrence.objects.count(), 0)
