from io import BytesIO
import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

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


class ICTStudentManagementTests(TestCase):
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
        self.student_user = self.User.objects.create_user(
            username='studentuser',
            password=self.password,
            role=self.User.Role.STUDENT,
        )
        self.program = Program.objects.create(
            name='Bachelor of Arts',
            code='BA',
            duration_years=4,
        )
        self.profile = self.create_profile('BA001')
        self.paths = [
            reverse('ict_students'),
            reverse('ict_student_add'),
            reverse('ict_student_edit', args=[self.profile.pk]),
            reverse('ict_student_deactivate', args=[self.profile.pk]),
            reverse('ict_student_reactivate', args=[self.profile.pk]),
            reverse('ict_student_reset_password', args=[self.profile.pk]),
        ]

    def create_profile(self, matric_number='BA001', **kwargs):
        user = self.User.objects.create_user(
            username=matric_number,
            password=self.password,
            first_name='Student',
            last_name='Example',
            role=self.User.Role.STUDENT,
        )
        return StudentProfile.objects.create(
            user=user,
            matric_number=matric_number,
            program=self.program,
            year_of_study=1,
            **kwargs,
        )

    def create_form_data(self, matric_number='BA100', **kwargs):
        data = {
            'first_name': 'New',
            'last_name': 'Student',
            'matric_number': matric_number,
            'program': self.program.pk,
            'year_of_study': 2,
            'temporary_password': 'Excellent-Temporary-Password-2026!',
        }
        data.update(kwargs)
        return data

    def post_student_create(self, data=None, files=None):
        self.client.force_login(self.ict)
        return self.client.post(
            reverse('ict_student_add'),
            data or self.create_form_data(),
            files or {},
        )

    def test_every_student_url_forbids_library_and_student_and_redirects_anonymous(self):
        for path in self.paths:
            with self.subTest(path=path):
                self.client.force_login(self.library)
                self.assertEqual(self.client.get(path).status_code, 403)
                self.client.force_login(self.student_user)
                self.assertEqual(self.client.get(path).status_code, 403)
                self.client.logout()
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(f'{reverse("login")}?next='))

    def test_student_deactivate_reactivate_and_password_reset_are_post_only(self):
        self.client.force_login(self.ict)
        for name in (
            'ict_student_deactivate',
            'ict_student_reactivate',
            'ict_student_reset_password',
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=[self.profile.pk]))
                self.assertEqual(response.status_code, 405)

    def test_ict_can_render_student_pages_and_clearance_is_read_only_text(self):
        self.client.force_login(self.ict)
        for path in (
            reverse('ict_students'),
            reverse('ict_student_add'),
            reverse('ict_student_edit', args=[self.profile.pk]),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'csrfmiddlewaretoken')
        list_response = self.client.get(
            reverse('ict_students'),
            {'program': self.program.pk, 'status': StudentProfile.Status.ACTIVE},
        )
        self.assertContains(list_response, 'BA001')
        self.assertContains(list_response, 'Not cleared')
        self.assertNotContains(
            self.client.get(reverse('ict_student_edit', args=[self.profile.pk])),
            'clinic_clearance',
        )

    def test_student_list_search_and_paginates_25_per_page(self):
        extra_users = [
            self.User(
                username=f'BA{number:03d}',
                password='!',
                first_name='Page',
                last_name='Student',
                role=self.User.Role.STUDENT,
            )
            for number in range(100, 125)
        ]
        extra_users = self.User.objects.bulk_create(extra_users)
        StudentProfile.objects.bulk_create([
            StudentProfile(
                user=user,
                matric_number=user.username,
                program=self.program,
                year_of_study=1,
            )
            for user in extra_users
        ])
        self.client.force_login(self.ict)
        response = self.client.get(reverse('ict_students'))
        self.assertEqual(response.context['page_obj'].paginator.per_page, 25)
        self.assertEqual(len(response.context['students']), 25)
        second_page = self.client.get(reverse('ict_students'), {'page': 2})
        self.assertEqual(len(second_page.context['students']), 1)
        self.assertContains(
            self.client.get(reverse('ict_students'), {'q': 'BA001'}),
            'BA001',
        )
        self.assertContains(
            self.client.get(reverse('ict_students'), {'q': 'Student Example'}),
            'BA001',
        )

    def test_add_creates_student_user_and_profile_with_uppercase_matric(self):
        self.client.force_login(self.ict)
        response = self.client.post(
            reverse('ict_student_add'),
            self.create_form_data('ba100'),
        )
        self.assertRedirects(response, reverse('ict_students'))
        user = self.User.objects.get(username='BA100')
        profile = StudentProfile.objects.get(matric_number='BA100')
        self.assertEqual(user.role, self.User.Role.STUDENT)
        self.assertTrue(user.must_change_password)
        self.assertEqual(profile.user_id, user.pk)
        self.assertTrue(AuditLog.objects.filter(
            actor=self.ict,
            action='create',
            target_type='StudentProfile',
            target_id=str(profile.pk),
        ).exists())

    def test_creation_rolls_back_user_when_profile_save_fails(self):
        self.client.force_login(self.ict)
        with patch.object(
            StudentProfile,
            'save',
            side_effect=ValidationError('Profile save failed.'),
        ):
            with self.assertRaises(ValidationError):
                self.client.post(
                    reverse('ict_student_add'),
                    self.create_form_data('BAFAIL'),
                )
        self.assertFalse(self.User.objects.filter(username='BAFAIL').exists())
        self.assertFalse(StudentProfile.objects.filter(matric_number='BAFAIL').exists())

    def test_duplicate_matric_is_rejected_case_insensitively(self):
        self.client.force_login(self.ict)
        response = self.client.post(
            reverse('ict_student_add'),
            self.create_form_data('ba001'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.User.objects.filter(username__iexact='BA001').count(), 1)
        self.assertEqual(StudentProfile.objects.filter(matric_number__iexact='BA001').count(), 1)

    def test_year_above_program_duration_is_rejected(self):
        self.client.force_login(self.ict)
        response = self.client.post(
            reverse('ict_student_add'),
            self.create_form_data('BA101', year_of_study=5),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.User.objects.filter(username='BA101').exists())

    def test_temporary_password_uses_django_password_validators(self):
        self.client.force_login(self.ict)
        response = self.client.post(
            reverse('ict_student_add'),
            self.create_form_data('BA105', temporary_password='short'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.User.objects.filter(username='BA105').exists())

    def test_non_image_named_jpg_is_rejected(self):
        upload = SimpleUploadedFile(
            'not-an-image.jpg',
            b'not actually a JPEG image',
            content_type='image/jpeg',
        )
        self.client.force_login(self.ict)
        data = self.create_form_data('BA102')
        data['passport_photo'] = upload
        response = self.client.post(
            reverse('ict_student_add'),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.User.objects.filter(username='BA102').exists())

    def test_photo_over_2_mb_is_rejected(self):
        image_buffer = BytesIO()
        pixels = os.urandom(1200 * 1200 * 3)
        Image.frombytes('RGB', (1200, 1200), pixels).save(image_buffer, format='PNG')
        self.assertGreater(len(image_buffer.getvalue()), 2 * 1024 * 1024)
        upload = SimpleUploadedFile(
            'large.png',
            image_buffer.getvalue(),
            content_type='image/png',
        )
        self.client.force_login(self.ict)
        data = self.create_form_data('BA103')
        data['passport_photo'] = upload
        response = self.client.post(
            reverse('ict_student_add'),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.User.objects.filter(username='BA103').exists())

    def test_uploaded_photo_is_resized_to_fit_400_by_400(self):
        image_buffer = BytesIO()
        Image.new('RGB', (800, 600), color='blue').save(image_buffer, format='JPEG')
        upload = SimpleUploadedFile(
            'passport.jpg',
            image_buffer.getvalue(),
            content_type='image/jpeg',
        )
        self.client.force_login(self.ict)
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            data = self.create_form_data('BA104')
            data['passport_photo'] = upload
            response = self.client.post(
                reverse('ict_student_add'),
                data,
            )
            self.assertRedirects(response, reverse('ict_students'))
            profile = StudentProfile.objects.get(matric_number='BA104')
            with Image.open(profile.passport_photo.path) as saved_photo:
                self.assertLessEqual(saved_photo.width, 400)
                self.assertLessEqual(saved_photo.height, 400)

    def test_posted_clinic_clearance_is_ignored_when_editing(self):
        self.profile.clinic_clearance = StudentProfile.ClinicClearance.CLEARED
        self.profile.save(update_fields=['clinic_clearance'])
        self.client.force_login(self.ict)
        response = self.client.post(
            reverse('ict_student_edit', args=[self.profile.pk]),
            {
                'first_name': 'Updated',
                'last_name': 'Student',
                'matric_number': self.profile.matric_number,
                'program': self.program.pk,
                'year_of_study': 1,
                'clinic_clearance': StudentProfile.ClinicClearance.NOT_CLEARED,
            },
        )
        self.assertRedirects(response, reverse('ict_students'))
        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.clinic_clearance,
            StudentProfile.ClinicClearance.CLEARED,
        )

    def test_replacing_photo_deletes_old_file_and_audits_photo_change(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            old_buffer = BytesIO()
            Image.new('RGB', (500, 300), color='red').save(old_buffer, format='JPEG')
            self.profile.passport_photo = SimpleUploadedFile(
                'old.jpg',
                old_buffer.getvalue(),
                content_type='image/jpeg',
            )
            self.profile.save()
            old_path = self.profile.passport_photo.path

            new_buffer = BytesIO()
            Image.new('RGB', (600, 400), color='green').save(new_buffer, format='PNG')
            data = {
                'first_name': 'Updated',
                'last_name': 'Student',
                'matric_number': self.profile.matric_number,
                'program': self.program.pk,
                'year_of_study': 1,
                'passport_photo': SimpleUploadedFile(
                    'new.png',
                    new_buffer.getvalue(),
                    content_type='image/png',
                ),
            }
            self.client.force_login(self.ict)
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse('ict_student_edit', args=[self.profile.pk]),
                    data,
                )

            self.assertRedirects(response, reverse('ict_students'))
            self.assertFalse(os.path.exists(old_path))
            self.assertTrue(AuditLog.objects.filter(
                target_type='StudentProfile',
                target_id=str(self.profile.pk),
                action='photo_change',
            ).exists())

    def test_edit_changes_username_and_deactivation_reactivation_status(self):
        self.client.force_login(self.ict)
        response = self.client.post(
            reverse('ict_student_edit', args=[self.profile.pk]),
            {
                'first_name': 'Updated',
                'last_name': 'Student',
                'matric_number': 'BA002',
                'program': self.program.pk,
                'year_of_study': 3,
            },
        )
        self.assertRedirects(response, reverse('ict_students'))
        self.profile.refresh_from_db()
        self.profile.user.refresh_from_db()
        self.assertEqual(self.profile.matric_number, 'BA002')
        self.assertEqual(self.profile.user.username, 'BA002')
        self.assertRedirects(
            self.client.post(reverse('ict_student_deactivate', args=[self.profile.pk])),
            reverse('ict_students'),
        )
        self.profile.refresh_from_db()
        self.profile.user.refresh_from_db()
        self.assertEqual(self.profile.status, StudentProfile.Status.DEACTIVATED)
        self.assertFalse(self.profile.user.is_active)
        self.assertRedirects(
            self.client.post(reverse('ict_student_reactivate', args=[self.profile.pk])),
            reverse('ict_students'),
        )
        self.profile.refresh_from_db()
        self.profile.user.refresh_from_db()
        self.assertEqual(self.profile.status, StudentProfile.Status.ACTIVE)
        self.assertTrue(self.profile.user.is_active)
        for action in ('edit', 'deactivate', 'reactivate'):
            with self.subTest(action=action):
                log = AuditLog.objects.get(
                    target_type='StudentProfile',
                    target_id=str(self.profile.pk),
                    action=action,
                )
                self.assertTrue(log.old_value)
                self.assertTrue(log.new_value)

    def test_password_reset_is_audited_without_password_values(self):
        self.client.force_login(self.ict)
        create_password = 'Initial-Temporary-Password-2026!'
        response = self.client.post(
            reverse('ict_student_add'),
            self.create_form_data(
                'BA106',
                temporary_password=create_password,
            ),
        )
        self.assertRedirects(response, reverse('ict_students'))
        profile = StudentProfile.objects.get(matric_number='BA106')
        temporary_password = 'Reset-Temporary-Password-2026!'
        response = self.client.post(
            reverse('ict_student_reset_password', args=[profile.pk]),
            {
                'password1': temporary_password,
                'password2': temporary_password,
            },
        )
        self.assertRedirects(response, reverse('ict_students'))
        profile.user.refresh_from_db()
        self.assertTrue(profile.user.check_password(temporary_password))
        self.assertTrue(profile.user.must_change_password)
        logs = AuditLog.objects.filter(
            target_type='StudentProfile',
            target_id=str(profile.pk),
        )
        values = ' '.join(
            logs.values_list('old_value', flat=True)
        ) + ' ' + ' '.join(logs.values_list('new_value', flat=True))
        self.assertNotIn(create_password, values)
        self.assertNotIn(temporary_password, values)
        self.assertNotIn(profile.user.password, values)
        self.assertTrue(logs.filter(action='create').exists())
        self.assertTrue(logs.filter(action='password_reset').exists())
