"""
Cin7 Django Admin Configuration - Updated for Comprehensive Models
"""

from django.contrib import admin
from .models import (
    ProductCategory,
    Branch,
    Product,
    ProductOption,
    Contact,
    SalesOrder,
    PurchaseOrder,
    Stock
)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['cin7_id', 'name', 'parent', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'cin7_id']
    ordering = ['name']


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['cin7_id', 'name', 'code', 'city', 'country', 'is_active']
    list_filter = ['is_active', 'country', 'created_at']
    search_fields = ['name', 'code', 'city', 'cin7_id']
    ordering = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'cin7_id', 'style_code', 'name', 'brand', 'category',
        'status', 'order_type', 'last_synced_at'
    ]
    list_filter = [
        'status', 'order_type', 'brand', 'category', 'created_at'
    ]
    search_fields = ['style_code', 'name', 'brand', 'cin7_id', 'tags']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at', 'cin7_created_date', 'cin7_modified_date']

    fieldsets = (
        ('Cin7 Information', {
            'fields': ('cin7_id', 'style_code', 'name', 'description', 'tags')
        }),
        ('Status & Dates', {
            'fields': ('status', 'cin7_created_date', 'cin7_modified_date', 'last_synced_at')
        }),
        ('Classification', {
            'fields': ('brand', 'category', 'sub_category', 'category_id_array')
        }),
        ('Supplier', {
            'fields': ('supplier_id', 'supplier_code')
        }),
        ('Physical Dimensions', {
            'fields': ('weight', 'height', 'width', 'length', 'volume'),
            'classes': ('collapse',)
        }),
        ('Inventory Control', {
            'fields': ('stock_control', 'order_type', 'product_type', 'product_subtype')
        }),
        ('Product Options', {
            'fields': ('option_label_1', 'option_label_2', 'option_label_3'),
            'classes': ('collapse',)
        }),
        ('Accounting', {
            'fields': ('sales_account', 'purchases_account', 'import_customs_duty'),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('images', 'pdf_upload', 'pdf_description'),
            'classes': ('collapse',)
        }),
        ('Custom Fields', {
            'fields': ('custom_fields',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductOption)
class ProductOptionAdmin(admin.ModelAdmin):
    list_display = [
        'cin7_id', 'code', 'product', 'option_1', 'option_2', 'option_3',
        'retail_price', 'stock_available', 'status'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['code', 'barcode', 'product__name', 'cin7_id']
    ordering = ['product', 'code']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at', 'cin7_created_date', 'cin7_modified_date']

    fieldsets = (
        ('Cin7 Information', {
            'fields': ('cin7_id', 'product', 'code', 'barcode', 'supplier_code')
        }),
        ('Status & Dates', {
            'fields': ('status', 'cin7_created_date', 'cin7_modified_date', 'last_synced_at')
        }),
        ('Variant Attributes', {
            'fields': ('option_1', 'option_2', 'option_3', 'size', 'size_id')
        }),
        ('Pricing', {
            'fields': ('retail_price', 'wholesale_price', 'vip_price', 'cost_price',
                       'special_price', 'specials_start_date', 'special_days', 'price_columns')
        }),
        ('Stock', {
            'fields': ('stock_available', 'stock_on_hand')
        }),
        ('Physical', {
            'fields': ('option_weight',),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('image',),
            'classes': ('collapse',)
        }),
        ('UOM', {
            'fields': ('uom_options',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = [
        'cin7_id', 'company', 'first_name', 'last_name',
        'type', 'email', 'is_active'
    ]
    list_filter = [
        'is_active', 'type', 'created_at'
    ]
    search_fields = ['company', 'first_name', 'last_name', 'email', 'cin7_id']
    ordering = ['company', 'last_name', 'first_name']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at', 'cin7_created_date', 'cin7_modified_date', 'balance_owing']

    fieldsets = (
        ('Cin7 Information', {
            'fields': ('cin7_id', 'type', 'company', 'first_name', 'last_name', 'job_title')
        }),
        ('Status & Dates', {
            'fields': ('is_active', 'cin7_created_date', 'cin7_modified_date', 'last_synced_at')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'mobile', 'fax', 'website')
        }),
        ('Business Information', {
            'fields': ('sales_person_id', 'account_number', 'group', 'sub_group', 'stages')
        }),
        ('Address', {
            'fields': ('address_line_1', 'address_line_2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Delivery Address', {
            'fields': ('delivery_first_name', 'delivery_last_name', 'delivery_company',
                      'delivery_address_1', 'delivery_address_2', 'delivery_city',
                      'delivery_state', 'delivery_postal_code', 'delivery_country'),
            'classes': ('collapse',)
        }),
        ('Billing Address', {
            'fields': ('billing_first_name', 'billing_last_name',
                      'billing_address_1', 'billing_address_2', 'billing_city',
                      'billing_state', 'billing_postal_code', 'billing_country'),
            'classes': ('collapse',)
        }),
        ('Billing Information', {
            'fields': ('billing_id', 'billing_company', 'accounts_first_name', 'accounts_last_name',
                      'billing_email', 'accounts_phone', 'billing_cost_center', 'cost_center'),
            'classes': ('collapse',)
        }),
        ('Pricing & Terms', {
            'fields': ('price_column', 'percentage_off', 'payment_terms')
        }),
        ('Financial', {
            'fields': ('tax_status', 'tax_number', 'credit_limit', 'balance_owing', 'on_hold')
        }),
        ('Accounting Integration', {
            'fields': ('accounting_integration_id',),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('comments',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = [
        'cin7_id', 'reference', 'customer', 'company',
        'created_date', 'total', 'status', 'stage'
    ]
    list_filter = ['status', 'stage', 'created_date', 'branch', 'is_void', 'is_approved']
    search_fields = ['reference', 'company', 'email', 'cin7_id']
    ordering = ['-created_date']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at', 'created_date', 'modified_date', 'cancellation_date', 'status']

    fieldsets = (
        ('Cin7 Information', {
            'fields': ('cin7_id', 'reference')
        }),
        ('Status & Workflow', {
            'fields': ('status', 'stage', 'is_approved', 'is_void', 'created_by', 'processed_by')
        }),
        ('Dates', {
            'fields': ('created_date', 'modified_date', 'cancellation_date', 'last_synced_at')
        }),
        ('Customer', {
            'fields': ('customer', 'member_id', 'member_email', 'first_name', 'last_name',
                      'company', 'email', 'phone', 'mobile', 'fax')
        }),
        ('Delivery Address', {
            'fields': ('delivery_first_name', 'delivery_last_name', 'delivery_company',
                      'delivery_address_1', 'delivery_address_2', 'delivery_city',
                      'delivery_state', 'delivery_postal_code', 'delivery_country')
        }),
        ('Billing Address', {
            'fields': ('billing_first_name', 'billing_last_name', 'billing_company',
                      'billing_address_1', 'billing_address_2', 'billing_city',
                      'billing_state', 'billing_postal_code', 'billing_country'),
            'classes': ('collapse',)
        }),
        ('Financial', {
            'fields': ('product_total', 'freight_total', 'surcharge', 'discount_total',
                      'tax_total', 'total', 'tax_rate', 'tax_status',
                      'currency', 'currency_rate')
        }),
        ('Payment & Shipping', {
            'fields': ('payment_method', 'payment_terms', 'branch', 'carrier', 'tracking_number')
        }),
        ('Notes', {
            'fields': ('customer_notes', 'internal_notes'),
            'classes': ('collapse',)
        }),
        ('Accounting', {
            'fields': ('accounting_integration_id',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        'cin7_id', 'reference', 'supplier', 'company',
        'order_date', 'total', 'status', 'stage'
    ]
    list_filter = ['status', 'stage', 'order_date', 'branch', 'is_void', 'is_approved']
    search_fields = ['reference', 'company', 'email', 'cin7_id']
    ordering = ['-order_date']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at', 'created_date', 'modified_date', 'status']

    fieldsets = (
        ('Cin7 Information', {
            'fields': ('cin7_id', 'reference')
        }),
        ('Status & Workflow', {
            'fields': ('status', 'stage', 'is_approved', 'is_void', 'created_by', 'processed_by')
        }),
        ('Dates', {
            'fields': ('created_date', 'modified_date', 'order_date', 'expected_date', 'received_date', 'last_synced_at')
        }),
        ('Supplier', {
            'fields': ('supplier', 'member_id', 'member_email', 'first_name', 'last_name',
                      'company', 'email', 'phone', 'mobile', 'fax')
        }),
        ('Delivery Address', {
            'fields': ('delivery_first_name', 'delivery_last_name', 'delivery_company',
                      'delivery_address_1', 'delivery_address_2', 'delivery_city',
                      'delivery_state', 'delivery_postal_code', 'delivery_country')
        }),
        ('Billing Address', {
            'fields': ('billing_first_name', 'billing_last_name', 'billing_company',
                      'billing_address_1', 'billing_address_2', 'billing_city',
                      'billing_state', 'billing_postal_code', 'billing_country'),
            'classes': ('collapse',)
        }),
        ('Financial', {
            'fields': ('product_total', 'freight_total', 'surcharge', 'discount_total',
                      'tax_total', 'total', 'tax_rate', 'tax_status',
                      'currency', 'currency_rate')
        }),
        ('Branch', {
            'fields': ('branch',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Accounting', {
            'fields': ('accounting_integration_id',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'product_name', 'branch_name',
        'available', 'stock_on_hand', 'open_sales', 'incoming',
        'last_synced_at'
    ]
    list_filter = ['branch', 'created_at']
    search_fields = ['code', 'barcode', 'product_name', 'branch_name', 'style_code']
    ordering = ['product_name', 'code', 'branch_name']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at', 'modified_date']

    fieldsets = (
        ('Product Information', {
            'fields': ('product', 'product_option', 'cin7_product_id', 'cin7_product_option_id',
                      'style_code', 'code', 'barcode', 'product_name')
        }),
        ('Variant Attributes', {
            'fields': ('option_1', 'option_2', 'option_3', 'size'),
            'classes': ('collapse',)
        }),
        ('Branch', {
            'fields': ('branch', 'cin7_branch_id', 'branch_name')
        }),
        ('Stock Levels', {
            'fields': ('available', 'stock_on_hand', 'open_sales', 'incoming', 'virtual', 'holding')
        }),
        ('Dates', {
            'fields': ('modified_date', 'last_synced_at')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
