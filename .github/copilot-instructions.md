# Project: TCNN-Portal

Django 5 web app (Python 3.10 or newer), SQLite for now, server-rendered templates, no separate frontend framework. It must start with an EMPTY database and contain no seed student or staff data. The Django project package is named tcnn_portal.

## Roles
ICT, LIBRARY, BURSARY, REGISTRY, CLINIC, STUDENT (stored on the custom User model).
Phase 1 builds screens for ICT, LIBRARY and STUDENT only. Other roles exist as choices but have no screens yet.

## Hard rules
1. Custom user model (AbstractUser) with a `role` field. Set AUTH_USER_MODEL before the first migration.
2. Only ICT creates accounts. No self-registration.
3. Permissions are enforced on the SERVER in every view (decorator or mixin). Hiding menu items is not enough.
4. STUDENT users only ever see their own data. Always use request.user. Never use an id from the URL or form to decide whose data to show.
5. ICT has full access EXCEPT medical history. ICT, Registry and Bursary see only clinic_clearance (Cleared / Not cleared). Only the CLINIC role may change clinic_clearance. Do not build a clinical history model yet.
6. class_label is computed, never typed or stored: program.code + str(year_of_study), e.g. "BA1".
7. Never hard-delete users or students. Deactivate instead.
8. Every create, edit, deactivate, role change and password reset writes an AuditLog row with actor, action, target, old value, new value, timestamp.
9. Passport photos: JPG or PNG only, max 2 MB, resized to max 400x400 with Pillow on upload.
10. CSRF protection on all forms. SECRET_KEY and DEBUG come from environment variables, never hard-coded.
11. Payments (later phase) are entered manually by Bursary. There is no payment gateway.
12. Write tests for every permission rule. Do not add features that were not requested.
