from django.conf import settings
from django.db import models


class SocialToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='social_tokens',
    )
    access_token = models.TextField()
    page_id = models.CharField(max_length=50)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'social_token'


class SystemConfig(models.Model):
    """Configuración a nivel de sistema (infraestructura compartida)."""
    key = models.CharField(max_length=100, primary_key=True)
    value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_config'


class UserConfig(models.Model):
    """Configuración por usuario (cada persona tiene sus propias variables)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='configs',
    )
    key = models.CharField(max_length=100)
    value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_config'
        unique_together = (('user', 'key'),)


class PublicationLog(models.Model):
    STATUS_CHOICES = [('SUCCESS', 'Success'), ('ERROR', 'Error'), ('SKIPPED', 'Skipped')]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='publication_logs',
    )
    executed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    post_id = models.CharField(max_length=100, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    competition_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'publication_log'
        ordering = ['-executed_at']


class FirstSolutionEvent(models.Model):
    """Registro de eventos First Solution (primer envío aceptado por problema)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='first_solution_events',
    )
    contest_key = models.CharField(max_length=50)
    problem_letter = models.CharField(max_length=10)
    problem_name = models.CharField(max_length=100, blank=True, default='')
    problem_color = models.CharField(max_length=20, blank=True, default='#CF1F4A')
    team_name = models.CharField(max_length=200)
    university = models.CharField(max_length=200, blank=True, default='')
    university_acronym = models.CharField(max_length=50, blank=True, default='')
    country_code = models.CharField(max_length=10, blank=True, default='')
    country_name = models.CharField(max_length=50, blank=True, default='')
    time_minutes = models.IntegerField(default=0)
    language = models.CharField(max_length=50, blank=True, default='')
    published_at = models.DateTimeField(auto_now_add=True)
    post_id = models.CharField(max_length=100, null=True, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'first_solution_event'
        unique_together = (('contest_key', 'problem_letter'),)
        ordering = ['time_minutes']


class CoachSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='coach_subscriptions',
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    teams = models.JSONField(default=list)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'coach_subscription'


class AllowedEmail(models.Model):
    """Lista de correos autorizados para autenticarse en el publicador."""
    email = models.EmailField(unique=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='added_allowed_emails',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'allowed_email'
        ordering = ['-created_at']

    def __str__(self):
        return self.email
