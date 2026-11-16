from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.conf import settings


def _process_passport_photo(upload):
    if upload.size > 2 * 1024 * 1024:
        raise ValidationError('Passport photos must be no larger than 2 MB.')

    extension = Path(upload.name).suffix.lower()
    if extension not in {'.jpg', '.jpeg', '.png'}:
        raise ValidationError('Passport photos must be JPG or PNG images.')

    try:
        with Image.open(upload.file) as image:
            image_format = image.format
            if image_format not in {'JPEG', 'PNG'}:
                raise ValidationError('Passport photos must be JPG or PNG images.')
            if (image_format == 'PNG') != (extension == '.png'):
                raise ValidationError('Passport photo extension must match its image format.')

            image.load()
            image = ImageOps.exif_transpose(image)
            image.thumbnail((400, 400), Image.Resampling.LANCZOS)
            if image_format == 'JPEG' and image.mode not in {'RGB', 'L'}:
                image = image.convert('RGB')

            output = BytesIO()
            image.save(output, format=image_format, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValidationError('Passport photo is not a valid image.') from error

    return ContentFile(output.getvalue(), name=upload.name)


class Program(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    duration_years = models.PositiveIntegerField()

    def __str__(self):
        return self.name


class StudentProfile(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed'
        DEACTIVATED = 'DEACTIVATED', 'Deactivated'

    class ClinicClearance(models.TextChoices):
        CLEARED = 'CLEARED', 'Cleared'
        NOT_CLEARED = 'NOT_CLEARED', 'Not cleared'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile',
    )
    matric_number = models.CharField(max_length=50, unique=True)
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='students')
    year_of_study = models.PositiveIntegerField()
    passport_photo = models.ImageField(upload_to='passports/')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    clinic_clearance = models.CharField(
        max_length=12,
        choices=ClinicClearance.choices,
        default=ClinicClearance.NOT_CLEARED,
    )

    @property
    def class_label(self):
        return f'{self.program.code}{self.year_of_study}'

    def __str__(self):
        return self.matric_number

    def save(self, *args, **kwargs):
        if self.passport_photo and not self.passport_photo._committed:
            upload = self.passport_photo
            processed_photo = _process_passport_photo(upload)
            self.passport_photo.save(upload.name, processed_photo, save=False)
        super().save(*args, **kwargs)


class AcademicSession(models.Model):
    name = models.CharField(max_length=50)
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=255)
    old_value = models.TextField()
    new_value = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
