from io import BytesIO
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from PIL import Image
from django.test import RequestFactory, TestCase
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .ict_views import ict_staff_deactivate, ict_staff_edit
from .models import AuditLog, Program, StudentProfile


class StudentProfileClassLabelTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(
            name='Bachelor of Arts',
            code='BA',
            duration_years=4,
        )
        self.user = get_user_model().objects.create_user(
            username='student',
            password='test-password',
        )

    def test_class_label_for_first_year(self):
        profile = StudentProfile.objects.create(
            user=self.user,
            matric_number='BA001',
            program=self.program,
            year_of_study=1,
        )

        self.assertEqual(profile.class_label, 'BA1')

    def test_class_label_for_second_year(self):
        profile = StudentProfile.objects.create(
            user=self.user,
            matric_number='BA002',
            program=self.program,
            year_of_study=2,
        )

        self.assertEqual(profile.class_label, 'BA2')

    def test_passport_photo_is_resized_on_upload(self):
        image_buffer = BytesIO()
        Image.new('RGB', (800, 600), color='blue').save(image_buffer, format='PNG')
        image_upload = SimpleUploadedFile(
            'passport.png',
            image_buffer.getvalue(),
            content_type='image/png',
        )

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            profile = StudentProfile.objects.create(
                user=self.user,
                matric_number='BA003',
                program=self.program,
                year_of_study=1,
                passport_photo=image_upload,
            )

            with Image.open(profile.passport_photo.path) as saved_image:
                self.assertEqual(saved_image.size, (400, 300))
                self.assertEqual(saved_image.format, 'PNG')

    def test_passport_photo_rejects_files_over_2_mb(self):
        large_upload = SimpleUploadedFile(
            'passport.jpg',
            b'x' * (2 * 1024 * 1024 + 1),
            content_type='image/jpeg',
        )

        with self.assertRaises(ValidationError):
            StudentProfile.objects.create(
                user=self.user,
                matric_number='BA004',
                program=self.program,
                year_of_study=1,
                passport_photo=large_upload,
            )


class ICTAdminAreaTests(TestCase):
    password = 'Some-Strong-Password-2026!'

    def setUp(self):
        self.User = get_user_model()
        self.ict = self.User.objects.create_user(
            username='ictadmin',
            password=self.password,
            role=self.User.Role.ICT,
        )
        self.library = self.User.objects.create_user(
            username='libraryuser',
            password=self.password,
            role=self.User.Role.LIBRARY,
        )
        self.student = self.User.objects.create_user(
            username='studentuser',
            password=self.password,
            role=self.User.Role.STUDENT,
        )
        self.staff = self.User.objects.create_user(
            username='staffuser',
            password=self.password,
            first_name='Taylor',
            last_name='Staff',
            role=self.User.Role.LIBRARY,
        )
        self.program = Program.objects.create(
            name='Bachelor of Arts',
            code='BA',
            duration_years=4,
        )
        self.paths = [
            reverse('ict_home'),
            reverse('ict_programs'),
            reverse('ict_program_add'),
            reverse('ict_program_edit', args=[self.program.pk]),
            reverse('ict_staff'),
            reverse('ict_staff_add'),
            reverse('ict_staff_edit', args=[self.staff.pk]),
            reverse('ict_staff_deactivate', args=[self.staff.pk]),
            reverse('ict_staff_reactivate', args=[self.staff.pk]),
            reverse('ict_staff_reset_password', args=[self.staff.pk]),
        ]

    def test_all_ict_urls_forbid_library_and_student_and_redirect_anonymous(self):
        for path in self.paths:
            with self.subTest(path=path):
                self.client.force_login(self.library)
                self.assertEqual(self.client.get(path).status_code, 403)
                self.client.force_login(self.student)
                self.assertEqual(self.client.get(path).status_code, 403)
                self.client.logout()
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(f'{reverse("login")}?next='))

    def test_staff_form_rejects_student_role(self):
        self.client.force_login(self.ict)
        response = self.client.post(reverse('ict_staff_add'), {
            'username': 'badrole',
            'first_name': 'Invalid',
            'last_name': 'Role',
            'role': self.User.Role.STUDENT,
            'password1': 'Unique-Temporary-Password-2026!',
            'password2': 'Unique-Temporary-Password-2026!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.User.objects.filter(username='badrole').exists())

        response = self.client.post(reverse('ict_staff_add'), {
            'username': 'weakpassword',
            'first_name': 'Weak',
            'last_name': 'Password',
            'role': self.User.Role.LIBRARY,
            'password1': 'short',
            'password2': 'short',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.User.objects.filter(username='weakpassword').exists())

    def test_staff_search_matches_name_and_username(self):
        self.client.force_login(self.ict)
        for query in ('Taylor Staff', 'staffuser'):
            with self.subTest(query=query):
                response = self.client.get(reverse('ict_staff'), {'q': query})
                self.assertContains(response, 'staffuser')

    def test_ict_cannot_deactivate_self(self):
        self.client.force_login(self.ict)
        response = self.client.post(reverse('ict_staff_deactivate', args=[self.ict.pk]))
        self.assertEqual(response.status_code, 403)
        self.ict.refresh_from_db()
        self.assertTrue(self.ict.is_active)

    def test_last_active_ict_cannot_be_deactivated_or_demoted(self):
        self.ict.is_active = False
        self.ict.save(update_fields=['is_active'])
        inactive_actor = self.User.objects.create_user(
            username='inactiveict',
            password=self.password,
            role=self.User.Role.ICT,
            is_active=False,
        )
        only_active_ict = self.User.objects.create_user(
            username='soleict',
            password=self.password,
            first_name='Only',
            last_name='ICT',
            role=self.User.Role.ICT,
        )
        inactive_actor_identity = SimpleNamespace(
            pk=inactive_actor.pk,
            role=self.User.Role.ICT,
            is_authenticated=True,
        )
        factory = RequestFactory()
        deactivate_request = factory.post(
            reverse('ict_staff_deactivate', args=[only_active_ict.pk]),
        )
        deactivate_request.user = inactive_actor_identity
        deactivate = ict_staff_deactivate(deactivate_request, only_active_ict.pk)
        self.assertEqual(deactivate.status_code, 403)
        edit_request = factory.post(
            reverse('ict_staff_edit', args=[only_active_ict.pk]),
            {
                'first_name': only_active_ict.first_name,
                'last_name': only_active_ict.last_name,
                'role': self.User.Role.LIBRARY,
            },
        )
        edit_request.user = inactive_actor_identity
        edit = ict_staff_edit(edit_request, only_active_ict.pk)
        self.assertEqual(edit.status_code, 403)
        only_active_ict.refresh_from_db()
        self.assertTrue(only_active_ict.is_active)
        self.assertEqual(only_active_ict.role, self.User.Role.ICT)

    def test_program_code_normalizes_and_rejects_invalid_values(self):
        self.client.force_login(self.ict)
        response = self.client.post(reverse('ict_program_add'), {
            'name': 'Business Administration',
            'code': 'ba2',
            'duration_years': 3,
        })
        self.assertRedirects(response, reverse('ict_programs'))
        self.assertTrue(Program.objects.filter(code='BA2').exists())
        self.assertTrue(AuditLog.objects.filter(
            target_type='Program',
            action='create',
            target_id=str(Program.objects.get(code='BA2').pk),
        ).exists())

        response = self.client.post(reverse('ict_program_add'), {
            'name': 'Invalid',
            'code': 'BA-3',
            'duration_years': 9,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Program.objects.filter(name='Invalid').exists())

    def test_deactivation_and_reactivation_do_not_accept_get(self):
        self.client.force_login(self.ict)
        self.assertEqual(
            self.client.get(reverse('ict_staff_deactivate', args=[self.staff.pk])).status_code,
            405,
        )
        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])
        self.assertEqual(
            self.client.get(reverse('ict_staff_reactivate', args=[self.staff.pk])).status_code,
            405,
        )

    def test_create_edit_deactivate_reactivate_and_reset_are_audited_safely(self):
        self.client.force_login(self.ict)
        initial_password = 'Brand-New-Temporary-Password-2026!'
        response = self.client.post(reverse('ict_staff_add'), {
            'username': 'newstaff',
            'first_name': 'New',
            'last_name': 'Staff',
            'role': self.User.Role.BURSARY,
            'password1': initial_password,
            'password2': initial_password,
        })
        self.assertRedirects(response, reverse('ict_staff'))
        created = self.User.objects.get(username='newstaff')
        self.assertTrue(created.must_change_password)

        response = self.client.post(
            reverse('ict_staff_edit', args=[created.pk]),
            {
                'first_name': 'Updated',
                'last_name': 'Staff',
                'role': self.User.Role.REGISTRY,
            },
        )
        self.assertRedirects(response, reverse('ict_staff'))

        self.assertRedirects(
            self.client.post(reverse('ict_staff_deactivate', args=[created.pk])),
            reverse('ict_staff'),
        )
        self.assertRedirects(
            self.client.post(reverse('ict_staff_reactivate', args=[created.pk])),
            reverse('ict_staff'),
        )

        reset_password = 'Another-Temporary-Password-2026!'
        self.assertRedirects(
            self.client.post(
                reverse('ict_staff_reset_password', args=[created.pk]),
                {
                    'password1': reset_password,
                    'password2': reset_password,
                },
            ),
            reverse('ict_staff'),
        )
        created.refresh_from_db()
        self.assertTrue(created.must_change_password)
        self.assertTrue(created.check_password(reset_password))

        program_edit = self.client.post(
            reverse('ict_program_edit', args=[self.program.pk]),
            {'name': self.program.name, 'code': 'ba', 'duration_years': 5},
        )
        self.assertRedirects(program_edit, reverse('ict_programs'))
        self.program.refresh_from_db()
        self.assertEqual(self.program.code, 'BA')
        self.assertEqual(self.program.duration_years, 5)

        actions = set(
            AuditLog.objects.filter(target_id=str(created.pk)).values_list('action', flat=True)
        )
        self.assertTrue({
            'create',
            'edit',
            'role_change',
            'deactivate',
            'reactivate',
            'password_reset',
        }.issubset(actions))
        self.assertTrue(AuditLog.objects.filter(
            target_type='Program',
            target_id=str(self.program.pk),
            action='edit',
        ).exists())

        audit_values = ' '.join(
            AuditLog.objects.values_list('old_value', flat=True)
        ) + ' ' + ' '.join(AuditLog.objects.values_list('new_value', flat=True))
        self.assertNotIn(initial_password, audit_values)
        self.assertNotIn(reset_password, audit_values)
        self.assertNotIn(created.password, audit_values)
