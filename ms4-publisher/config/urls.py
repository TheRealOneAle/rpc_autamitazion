from django.urls import path, include
from django.contrib.auth.decorators import login_required
from publisher.views import dashboard, configuracion
from publisher import google_auth

urlpatterns = [
    path('', login_required(dashboard), name='dashboard'),
    path('configuracion/', login_required(configuracion), name='configuracion'),
    path('login/', google_auth.login_page, name='login'),
    path('login/google/', google_auth.google_login, name='google_login'),
    path('login/google/callback/', google_auth.google_callback, name='google_callback'),
    path('logout/', google_auth.logout_view, name='logout'),
    path('api/', include('publisher.urls')),
]
