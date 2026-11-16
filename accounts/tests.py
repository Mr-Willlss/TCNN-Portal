from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from portal.models import AuditLog


class FirstRunSetupTests(TestCase):
    def setUp(self):
        self.setup_url = reverse('setup')
        self.password = 'V3ry-Long-Random-Setup-Password!2026'

    def setup_data(self):
        return {
            'first_name': 'Initial',
            'last_name': 'Administrator',
            'username': 'initial_ict',
            'password1': self.password,
            'password2': self.password,
        }

    def test_setup_page_creates_active_ict_user_and_audit_log(self):
        response = self.client.get(self.setup_url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(self.setup_url, self.setup_data())

        self.assertRedirects(response, reverse('login'))
        user = get_user_model().objects.get(username='initial_ict')
        self.assertEqual(user.role, get_user_model().Role.ICT)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(AuditLog.objects.filter(target_id=str(user.pk)).count(), 1)

    def test_setup_returns_404_after_ict_user_exists(self):
        get_user_model().objects.create_user(
            username='existing_ict',
            password=self.password,
            role=get_user_model().Role.ICT,
        )

        self.assertEqual(self.client.get(self.setup_url).status_code, 404)
        self.assertEqual(
            self.client.post(self.setup_url, self.setup_data()).status_code,
            404,
        )

    def test_other_urls_redirect_to_setup_before_first_ict_exists(self):
        for path in ('/accounts/login/', '/ict/', '/unmatched/', '/admin/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertRedirects(response, self.setup_url)

    def test_static_and_media_paths_are_exempt_from_setup_redirect(self):
        for path in ('/static/app.css', '/media/passports/photo.jpg'):
            with self.subTest(path=path):
                self.assertNotEqual(self.client.get(path).status_code, 302)

    def test_setup_validates_password_confirmation_and_password_strength(self):
        data = self.setup_data()
        data['password2'] = 'different-password'
        response = self.client.post(self.setup_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.exists())

        data = self.setup_data()
        data['password1'] = 'password'
        data['password2'] = 'password'
        response = self.client.post(self.setup_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.exists())


class RoleAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.ict = User.objects.create_user(
            username='ict',
            password='test-password',
            role=User.Role.ICT,
        )
        self.student = User.objects.create_user(
            username='student',
            password='test-password',
            role=User.Role.STUDENT,
        )
        self.library = User.objects.create_user(
            username='library',
            password='test-password',
            role=User.Role.LIBRARY,
        )

    def test_anonymous_users_are_redirected_to_login_from_role_pages(self):
        for path in ('/ict/', '/student/', '/library/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertRedirects(
                    response,
                    f'{reverse("login")}?next={path}',
                )

    def test_student_cannot_open_ict_or_library(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/ict/').status_code, 403)
        self.assertEqual(self.client.get('/library/').status_code, 403)
        self.assertEqual(self.client.get('/student/').status_code, 200)

    def test_library_cannot_open_ict_or_student(self):
        self.client.force_login(self.library)
        self.assertEqual(self.client.get('/ict/').status_code, 403)
        self.assertEqual(self.client.get('/student/').status_code, 403)
        self.assertEqual(self.client.get('/library/').status_code, 200)

    def test_ict_can_open_ict_and_library_pages(self):
        self.client.force_login(self.ict)
        self.assertEqual(self.client.get('/ict/').status_code, 200)
        self.assertEqual(self.client.get('/library/').status_code, 200)
        self.assertEqual(self.client.get('/student/').status_code, 403)

    def test_login_redirects_by_role(self):
        role_destinations = (
            (self.ict, 'ict_home'),
            (self.student, 'student_home'),
            (self.library, 'library_home'),
        )
        for user, destination in role_destinations:
            with self.subTest(role=user.role):
                self.client.logout()
                response = self.client.post(
                    reverse('login'),
                    {'username': user.username, 'password': 'test-password'},
                )
                self.assertRedirects(response, reverse(destination))

    def test_other_role_is_sent_to_no_screen_page(self):
        user = get_user_model().objects.create_user(
            username='clinic',
            password='test-password',
            role=get_user_model().Role.CLINIC,
        )
        response = self.client.post(
            reverse('login'),
            {'username': user.username, 'password': 'test-password'},
        )
        self.assertRedirects(response, reverse('no_screen'))
        self.assertContains(
            self.client.get(reverse('no_screen')),
            'Your account has no screens yet. Please contact ICT.',
        )

    def test_no_screen_page_requires_authentication(self):
        response = self.client.get(reverse('no_screen'))
        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("no_screen")}',
        )

    def test_admin_route_is_removed(self):
        self.assertEqual(self.client.get('/admin/').status_code, 404)

    def test_logout_requires_post(self):
        self.client.force_login(self.ict)
        self.assertEqual(self.client.get('/accounts/logout/').status_code, 405)
        response = self.client.post('/accounts/logout/')
        self.assertRedirects(response, reverse('login'))
