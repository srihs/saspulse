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

    # Sales Forecasting (AI/ML)
    path('forecasting/', views.sales_forecasting, name='sales_forecasting'),
    path('forecasting/products/<str:school_name>/', views.forecast_product_breakdown, name='forecast_product_breakdown'),

    # Replenishment Workflow
    path('replenishment/store/', views.store_manager_replenishment, name='store_replenishment'),
    path('replenishment/store/approve/<int:request_id>/', views.approve_replenishment, name='approve_replenishment'),
    path('replenishment/dp/', views.dp_team_replenishment, name='dp_replenishment'),
    path('replenishment/dp/approve/<int:request_id>/', views.dp_approve_replenishment, name='dp_approve_replenishment'),
]
