"""
Dashboard URL Configuration
"""

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('api/', views.dashboard_api, name='api'),
    path('refresh/', views.refresh_cache, name='refresh'),
    path('bts-forecasting/', views.bts_forecasting, name='bts_forecasting'),
]
