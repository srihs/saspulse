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
    # Old Replenishment System (Legacy)
    path('replenishment/store/', views.store_manager_replenishment, name='store_replenishment'),
    path('replenishment/store/approve/<int:request_id>/', views.approve_replenishment, name='approve_replenishment'),
    path('replenishment/dp/', views.dp_team_replenishment, name='dp_replenishment'),
    path('replenishment/dp/approve-item/<int:request_id>/', views.dp_approve_replenishment, name='dp_approve_replenishment'),

    # Store Replenishment Request System (New - Batch Based)
    path('replenishment/store/submit/', views.submit_store_replenishment_request, name='submit_store_replenishment_request'),
    path('replenishment/store/requests/', views.store_replenishment_requests_list, name='store_replenishment_requests_list'),
    path('replenishment/store/requests/<str:request_number>/', views.store_replenishment_request_detail, name='store_replenishment_request_detail'),
    path('replenishment/store/daily-pick-list/', views.store_daily_pick_list, name='store_daily_pick_list'),

    # DP Team Approval System (New - Batch Based)
    path('replenishment/dp/approval/', views.dp_replenishment_approval, name='dp_replenishment_approval'),
    path('replenishment/dp/requests/', views.dp_replenishment_requests_list, name='dp_replenishment_requests_list'),
    path('replenishment/dp/requests/<str:request_number>/', views.dp_replenishment_request_detail, name='dp_replenishment_request_detail'),
    path('replenishment/dp/approve/<int:batch_id>/', views.dp_approve_request, name='dp_approve_request'),
    path('replenishment/dp/reject/<int:batch_id>/', views.dp_reject_request, name='dp_reject_request'),

    # Analytics Reports
    path('reports/bts-sellthrough/', views.bts_sellthrough_report, name='bts_sellthrough_report'),
    path('reports/inventory-health/', views.inventory_health_dashboard, name='inventory_health_dashboard'),
    path('reports/inventory-alignment/', views.inventory_alignment_matrix, name='inventory_alignment_matrix'),

    # Stock Management Reports
    path('stocks/turn-rate/', views.stock_turn_rate_report, name='stock_turn_rate_report'),
    path('stocks/days-inventory/', views.days_of_inventory_report, name='days_of_inventory_report'),
    path('stocks/dead-stock/', views.dead_stock_report, name='dead_stock_report'),
    path('stocks/best-sellers/', views.top_best_sellers_report, name='top_best_sellers_report'),
    path('stocks/abc-analysis/', views.abc_analysis_report, name='abc_analysis_report'),
]
