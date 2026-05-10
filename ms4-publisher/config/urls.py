from django.urls import path, include
from publisher.views import dashboard

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('api/', include('publisher.urls')),
]
