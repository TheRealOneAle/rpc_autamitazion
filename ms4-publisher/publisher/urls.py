from django.urls import path
from .views import (
    preview_image, competition_stats,
    StatusView, TriggerView, LogsView, ConfigView, TokenView,
    CoachSubscribeView, CoachListView, CoachStatsView,
)

urlpatterns = [
    path('preview-image/', preview_image),
    path('competition-stats/', competition_stats),
    path('status/', StatusView.as_view()),
    path('trigger/', TriggerView.as_view()),
    path('logs/', LogsView.as_view()),
    path('config/', ConfigView.as_view()),
    path('token/', TokenView.as_view()),
    path('coaches/', CoachListView.as_view()),
    path('coaches/subscribe/', CoachSubscribeView.as_view()),
    path('coaches/<int:coach_id>/stats/', CoachStatsView.as_view()),
]
