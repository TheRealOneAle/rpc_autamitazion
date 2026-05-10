from django.db import models


class SocialToken(models.Model):
    access_token = models.TextField()
    page_id = models.CharField(max_length=50)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'social_token'


class SystemConfig(models.Model):
    key = models.CharField(max_length=100, primary_key=True)
    value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_config'


class PublicationLog(models.Model):
    STATUS_CHOICES = [('SUCCESS', 'Success'), ('ERROR', 'Error'), ('SKIPPED', 'Skipped')]
    executed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    post_id = models.CharField(max_length=100, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    competition_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'publication_log'
        ordering = ['-executed_at']


class CoachSubscription(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    teams = models.JSONField(default=list)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'coach_subscription'
