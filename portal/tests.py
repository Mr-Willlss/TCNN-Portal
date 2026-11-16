from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.test import TestCase
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Program, StudentProfile


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
