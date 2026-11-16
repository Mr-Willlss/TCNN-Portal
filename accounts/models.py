from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Role(models.TextChoices):
        ICT = 'ICT', 'ICT'
        LIBRARY = 'LIBRARY', 'Library'
        BURSARY = 'BURSARY', 'Bursary'
        REGISTRY = 'REGISTRY', 'Registry'
        CLINIC = 'CLINIC', 'Clinic'
        STUDENT = 'STUDENT', 'Student'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
