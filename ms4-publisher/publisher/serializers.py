from rest_framework import serializers
from .models import (
    SocialToken, SystemConfig, UserConfig, PublicationLog,
    CoachSubscription, AllowedEmail, FirstSolutionEvent,
)


class SocialTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialToken
        fields = ['id', 'page_id', 'expires_at', 'created_at', 'updated_at']


class SocialTokenWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialToken
        fields = ['access_token', 'page_id', 'expires_at']


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = ['key', 'value', 'updated_at']


class UserConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserConfig
        fields = ['key', 'value', 'updated_at']


class PublicationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicationLog
        fields = ['id', 'executed_at', 'status', 'post_id', 'error_message', 'competition_data']


class FirstSolutionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirstSolutionEvent
        fields = [
            'id', 'contest_key', 'problem_letter', 'problem_name', 'problem_color',
            'team_name', 'university', 'university_acronym', 'country_code', 'country_name',
            'time_minutes', 'language', 'published_at', 'post_id', 'success', 'error_message',
        ]


class CoachSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachSubscription
        fields = ['id', 'name', 'email', 'teams', 'active', 'created_at']


class AllowedEmailSerializer(serializers.ModelSerializer):
    added_by_username = serializers.ReadOnlyField(source='added_by.username')

    class Meta:
        model = AllowedEmail
        fields = ['id', 'email', 'is_active', 'created_at', 'added_by_username']
