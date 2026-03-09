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
    path('forecasting/filter-options/', views.forecasting_filter_options, name='forecasting_filter_options'),
    path('forecasting/products/<str:school_name>/', views.forecast_product_breakdown, name='forecast_product_breakdown'),
    path('forecasting/health/', views.forecast_health_dashboard, name='forecast_health'),
    path('forecasting/regenerate/', views.trigger_forecast_regeneration, name='trigger_regeneration'),
    path('forecasting/past-sales/', views.past_sales_data, name='past_sales_data'),

    # Replenishment Workflow
    path('replenishment/store/', views.store_manager_replenishment, name='store_replenishment'),
    path('replenishment/store/approve/<int:request_id>/', views.approve_replenishment, name='approve_replenishment'),
    path('replenishment/dp/', views.dp_team_replenishment, name='dp_replenishment'),
    path('replenishment/dp/approve/<int:request_id>/', views.dp_approve_replenishment, name='dp_approve_replenishment'),

    # Store Replenishment Request System
    path('replenishment/store/submit/', views.submit_store_replenishment_request, name='submit_store_replenishment_request'),
    path('replenishment/store/requests/', views.store_replenishment_requests_list, name='store_replenishment_requests_list'),
    path('replenishment/store/requests/<str:request_number>/', views.store_replenishment_request_detail, name='store_replenishment_request_detail'),

    # DP Team Approval System
    path('replenishment/dp/approval/', views.dp_replenishment_approval, name='dp_replenishment_approval'),
    path('replenishment/dp/approve/<int:batch_id>/', views.dp_approve_request, name='dp_approve_request'),
    path('replenishment/dp/reject/<int:batch_id>/', views.dp_reject_request, name='dp_reject_request'),

    # Analytics Reports
    path('reports/bts-sellthrough/', views.bts_sellthrough_report, name='bts_sellthrough_report'),
    path('reports/inventory-health/', views.inventory_health_dashboard, name='inventory_health_dashboard'),
    path('reports/inventory-alignment/', views.inventory_alignment_matrix, name='inventory_alignment_matrix'),
]
