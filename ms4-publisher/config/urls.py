from django.urls import path, include
from publisher.views import dashboard, configuracion

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('configuracion/', configuracion, name='configuracion'),
    path('api/', include('publisher.urls')),
]
