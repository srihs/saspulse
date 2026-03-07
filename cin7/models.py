"""
Cin7 Django Models - COMPREHENSIVE VERSION
All available fields from Cin7 API

Models representing Cin7 entities with complete field coverage:
- Product: Products/inventory items with all Cin7 fields
- ProductOption: Product variants/options
- ProductCategory: Product categories
- Branch: Warehouses/locations
- Contact: Customers and suppliers with full contact data
- SalesOrder: Sales orders with all financial and shipping fields
- SalesOrderLine: Line items for sales orders
- PurchaseOrder: Purchase orders with complete data
- PurchaseOrderLine: Line items for purchase orders
- Stock: Inventory/stock levels per branch
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class TimestampedModel(models.Model):
    """Abstract base model with created/updated timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ==================== PRODUCT CATEGORY ====================

class ProductCategoryManager(models.Manager):
    """Custom manager for ProductCategory"""

    def get_active(self):
        """Get all active categories"""
        return self.filter(is_active=True)


class ProductCategory(TimestampedModel):
    """Product categories from Cin7"""
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 category ID")
    name = models.CharField(max_length=255, db_index=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(default=True)

    objects = ProductCategoryManager()

    class Meta:
        db_table = 'cin7_sync_productcategory'
        verbose_name_plural = "Product Categories"
        ordering = ['name']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name


# ==================== BRANCH ====================

class BranchManager(models.Manager):
    """Custom manager for Branch"""

    def get_active(self):
        """Get all active branches"""
        return self.filter(is_active=True)


class Branch(TimestampedModel):
    """Warehouses/branches from Cin7"""
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 branch ID")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    objects = BranchManager()

    class Meta:
        db_table = 'cin7_sync_branch'
        verbose_name_plural = "Branches"
        ordering = ['name']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ==================== PRODUCT ====================

class ProductManager(models.Manager):
    """Custom manager for Product"""

    def get_active(self):
        """Get all active products"""
        return self.filter(status='Public')

    def get_low_stock(self, threshold=10):
        """Get products with stock below threshold"""
        return self.filter(stock_quantity__lt=threshold, status='Public')

    def get_by_brand(self, brand):
        """Get products by brand"""
        return self.filter(brand__iexact=brand, status='Public')


class Product(TimestampedModel):
    """
    Products from Cin7 - Complete field coverage
    Based on https://api.cin7.com/API/Help/Api/GET-v1-Products_fields_where_order_page_rows
    """

    STATUS_CHOICES = [
        ('Inactive', 'Inactive'),
        ('Public', 'Public'),
        ('ShowInB2B', 'Show in B2B'),
        ('Internal', 'Internal'),
    ]

    ORDER_TYPE_CHOICES = [
        ('Order', 'Order'),
        ('Kit', 'Kit'),
        ('Limited Stock', 'Limited Stock'),
        ('Buy To Order', 'Buy To Order'),
        ('Pre-order', 'Pre-order'),
        ('Gift Voucher', 'Gift Voucher'),
    ]

    # Core Identifiers
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 product ID")
    style_code = models.CharField(max_length=100, blank=True, db_index=True, help_text="Product style identifier")
    name = models.CharField(max_length=250, db_index=True)

    # Status & Dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Public', db_index=True)
    cin7_created_date = models.DateTimeField(null=True, blank=True)
    cin7_modified_date = models.DateTimeField(null=True, blank=True)

    # Description & Content
    description = models.TextField(blank=True)
    tags = models.TextField(blank=True, help_text="Comma delimited list of custom tags")

    # Classification
    brand = models.CharField(max_length=250, blank=True, db_index=True)
    category = models.CharField(max_length=250, blank=True, db_index=True)
    category_id = models.BigIntegerField(null=True, blank=True, db_index=True, help_text="Primary category ID")
    category_name = models.CharField(max_length=255, blank=True, db_index=True, help_text="Primary category name (e.g., 'Avondale Shop')")
    sub_category = models.CharField(max_length=250, blank=True)
    category_id_array = models.JSONField(default=list, blank=True, help_text="Array of category IDs")

    # Supplier
    supplier_id = models.IntegerField(null=True, blank=True)
    supplier_code = models.CharField(max_length=100, blank=True)

    # Sales Channels
    channels = models.TextField(blank=True, help_text="Selling channels list")

    # Physical Dimensions
    weight = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(999)]
    )
    height = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(999)]
    )
    width = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(999)]
    )
    length = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(999)]
    )
    volume = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(999)]
    )

    # Inventory Control
    stock_control = models.CharField(max_length=50, blank=True, help_text="Stock control type")
    order_type = models.CharField(max_length=50, choices=ORDER_TYPE_CHOICES, default='Order')
    product_type = models.CharField(max_length=100, blank=True)
    product_subtype = models.CharField(max_length=100, blank=True)

    # Project Association
    project_name = models.CharField(max_length=250, blank=True)

    # Product Options/Variants Configuration
    option_label_1 = models.CharField(max_length=100, blank=True, help_text="e.g., Color")
    option_label_2 = models.CharField(max_length=100, blank=True, help_text="e.g., Size")
    option_label_3 = models.CharField(max_length=100, blank=True, help_text="e.g., Fabric")

    # Accounting
    sales_account = models.CharField(max_length=100, blank=True)
    purchases_account = models.CharField(max_length=100, blank=True)
    import_customs_duty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Product cost price")

    # Size Range
    size_range_id = models.IntegerField(null=True, blank=True)

    # Custom Fields
    custom_fields = models.JSONField(default=dict, blank=True, help_text="Custom field key-value pairs")

    # Media
    images = models.JSONField(default=list, blank=True, help_text="Array of image URLs")
    pdf_upload = models.URLField(max_length=500, blank=True)
    pdf_description = models.TextField(blank=True)

    # Metadata
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = ProductManager()

    class Meta:
        db_table = 'cin7_sync_product'
        ordering = ['name']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['style_code']),
            models.Index(fields=['name']),
            models.Index(fields=['brand']),
            models.Index(fields=['category']),
            models.Index(fields=['status']),
            models.Index(fields=['last_synced_at']),
        ]

    def __str__(self):
        return f"{self.style_code} - {self.name}" if self.style_code else self.name

    def mark_synced(self):
        """Mark product as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])


# ==================== PRODUCT OPTION (Variants) ====================

class ProductOptionManager(models.Manager):
    """Custom manager for ProductOption"""

    def get_active(self):
        """Get all active product options"""
        return self.filter(status='Public')

    def get_in_stock(self):
        """Get options with stock available"""
        return self.filter(stock_available__gt=0, status='Public')


class ProductOption(TimestampedModel):
    """
    Product Options/Variants from Cin7
    Represents SKUs, pricing, and stock for product variants
    """

    STATUS_CHOICES = [
        ('Inactive', 'Inactive'),
        ('Public', 'Public'),
        ('ShowInB2B', 'Show in B2B'),
        ('Internal', 'Internal'),
    ]

    # Core Identifiers
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 product option ID")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='options')

    # Codes & Identifiers
    code = models.CharField(max_length=100, unique=True, db_index=True, help_text="SKU/Product code")
    barcode = models.CharField(max_length=100, blank=True, db_index=True, help_text="UPC/EAN")
    supplier_code = models.CharField(max_length=100, blank=True)

    # Status & Dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Public', db_index=True)
    cin7_created_date = models.DateTimeField(null=True, blank=True)
    cin7_modified_date = models.DateTimeField(null=True, blank=True)

    # Variant Attributes
    option_1 = models.CharField(max_length=50, blank=True, help_text="e.g., Red")
    option_2 = models.CharField(max_length=50, blank=True, help_text="e.g., Large")
    option_3 = models.CharField(max_length=50, blank=True, help_text="e.g., Cotton")
    size = models.CharField(max_length=50, blank=True)
    size_id = models.IntegerField(null=True, blank=True)

    # Pricing
    retail_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vip_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    specials_start_date = models.DateField(null=True, blank=True)
    special_days = models.IntegerField(null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Stock
    stock_available = models.IntegerField(default=0, db_index=True)
    stock_on_hand = models.IntegerField(default=0)

    # Physical
    option_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Media
    image = models.URLField(max_length=500, blank=True)

    # UOM (Unit of Measure) Options
    uom_options = models.JSONField(default=list, blank=True)

    # Price Columns
    price_columns = models.JSONField(default=dict, blank=True, help_text="Custom price column values")

    # Metadata
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = ProductOptionManager()

    class Meta:
        db_table = 'cin7_sync_productoption'
        ordering = ['product', 'code']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['code']),
            models.Index(fields=['barcode']),
            models.Index(fields=['product']),
            models.Index(fields=['status']),
            models.Index(fields=['stock_available']),
        ]

    def __str__(self):
        return f"{self.code} - {self.product.name}"

    @property
    def is_on_special(self):
        """Check if product is currently on special"""
        if not self.special_price or not self.specials_start_date:
            return False
        today = timezone.now().date()
        end_date = self.specials_start_date + timezone.timedelta(days=self.special_days or 0)
        return self.specials_start_date <= today <= end_date

    def mark_synced(self):
        """Mark option as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])


# ==================== CONTACT ====================

class ContactManager(models.Manager):
    """Custom manager for Contact"""

    def get_customers(self):
        """Get all customers"""
        return self.filter(type='Customer', is_active=True)

    def get_suppliers(self):
        """Get all suppliers"""
        return self.filter(type='Supplier', is_active=True)


class Contact(TimestampedModel):
    """
    Customers and suppliers from Cin7 - Complete field coverage
    Based on https://api.cin7.com/api/Help/Api/GET-v1-Contacts_fields_where_order_page_rows
    """

    CONTACT_TYPE_CHOICES = [
        ('Customer', 'Customer'),
        ('Supplier', 'Supplier'),
    ]

    TAX_STATUS_CHOICES = [
        ('Incl', 'Tax Inclusive'),
        ('Excl', 'Tax Exclusive'),
        ('Exempt', 'Tax Exempt'),
    ]

    # Core Identifiers
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 contact ID")
    type = models.CharField(max_length=10, choices=CONTACT_TYPE_CHOICES, default='Customer', db_index=True)

    # Status & Dates
    is_active = models.BooleanField(default=True, db_index=True)
    cin7_created_date = models.DateTimeField(null=True, blank=True)
    cin7_modified_date = models.DateTimeField(null=True, blank=True)

    # Personal Information
    company = models.CharField(max_length=250, blank=True)
    first_name = models.CharField(max_length=250, blank=True)
    last_name = models.CharField(max_length=250, blank=True)
    job_title = models.CharField(max_length=250, blank=True)

    # Contact Details
    email = models.EmailField(max_length=250, blank=True, db_index=True)
    website = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)

    # Business Information
    sales_person_id = models.IntegerField(null=True, blank=True)
    account_number = models.CharField(max_length=10, blank=True)

    # Billing Information
    billing_id = models.IntegerField(null=True, blank=True, help_text="Parent company member reference")
    billing_company = models.CharField(max_length=50, blank=True)
    accounts_first_name = models.CharField(max_length=50, blank=True)
    accounts_last_name = models.CharField(max_length=50, blank=True)
    billing_email = models.EmailField(max_length=50, blank=True)
    accounts_phone = models.CharField(max_length=50, blank=True)
    billing_cost_center = models.CharField(max_length=100, blank=True, help_text="Alternative GL account")
    cost_center = models.CharField(max_length=100, blank=True, help_text="Alternative GL account")

    # Pricing & Discounts
    price_column = models.CharField(max_length=50, blank=True, help_text="Valid price column name")
    percentage_off = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # Financial Terms
    payment_terms = models.CharField(max_length=100, blank=True)
    tax_status = models.CharField(max_length=10, choices=TAX_STATUS_CHOICES, blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_owing = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Read-only")
    on_hold = models.BooleanField(default=False)

    # Classification
    group = models.CharField(max_length=100, blank=True)
    sub_group = models.CharField(max_length=100, blank=True)
    stages = models.CharField(max_length=100, blank=True)

    # Accounting Integration
    accounting_integration_id = models.JSONField(
        default=dict, blank=True,
        help_text="Integration IDs for Xero, QuickBooks Online, QuickBooks Desktop"
    )

    # Additional Address Fields (beyond basic contact)
    address_line_1 = models.CharField(max_length=250, blank=True)
    address_line_2 = models.CharField(max_length=250, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Delivery Address
    delivery_first_name = models.CharField(max_length=250, blank=True)
    delivery_last_name = models.CharField(max_length=250, blank=True)
    delivery_company = models.CharField(max_length=250, blank=True)
    delivery_address_1 = models.CharField(max_length=250, blank=True)
    delivery_address_2 = models.CharField(max_length=250, blank=True)
    delivery_city = models.CharField(max_length=250, blank=True)
    delivery_state = models.CharField(max_length=250, blank=True)
    delivery_postal_code = models.CharField(max_length=250, blank=True)
    delivery_country = models.CharField(max_length=250, blank=True)

    # Billing Address
    billing_first_name = models.CharField(max_length=250, blank=True)
    billing_last_name = models.CharField(max_length=250, blank=True)
    billing_address_1 = models.CharField(max_length=250, blank=True)
    billing_address_2 = models.CharField(max_length=250, blank=True)
    billing_city = models.CharField(max_length=250, blank=True)
    billing_state = models.CharField(max_length=250, blank=True)
    billing_postal_code = models.CharField(max_length=250, blank=True)
    billing_country = models.CharField(max_length=250, blank=True)

    # Comments & Notes
    comments = models.TextField(blank=True)

    # Metadata
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = ContactManager()

    class Meta:
        ordering = ['company', 'last_name', 'first_name']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['type']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
            models.Index(fields=['company']),
        ]

    def __str__(self):
        if self.company:
            return self.company
        return f"{self.first_name} {self.last_name}".strip() or f"Contact {self.cin7_id}"

    @property
    def full_name(self):
        """Get full name"""
        return f"{self.first_name} {self.last_name}".strip()

    def mark_synced(self):
        """Mark contact as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])


# ==================== SALES ORDER ====================

class SalesOrderManager(models.Manager):
    """Custom manager for SalesOrder"""

    def get_by_status(self, status):
        """Get orders by status"""
        return self.filter(status=status)

    def get_by_stage(self, stage):
        """Get orders by stage"""
        return self.filter(stage=stage)

    def get_by_date_range(self, start_date, end_date):
        """Get orders within date range"""
        return self.filter(created_date__range=[start_date, end_date])


class SalesOrder(TimestampedModel):
    """
    Sales orders from Cin7 - Complete field coverage
    Based on https://api.cin7.com/api/Help/Api/GET-v1-SalesOrders_fields_where_order_page_rows
    """

    STAGE_CHOICES = [
        ('New', 'New'),
        ('Awaiting Payment', 'Awaiting Payment'),
        ('Declined', 'Declined'),
        ('Dispatched', 'Dispatched'),
        ('Processing', 'Processing'),
        ('On Hold', 'On Hold'),
    ]

    TAX_STATUS_CHOICES = [
        ('Incl', 'Tax Inclusive'),
        ('Excl', 'Tax Exclusive'),
        ('Exempt', 'Tax Exempt'),
    ]

    # Core Identifiers
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 sales order ID")
    reference = models.CharField(max_length=30, unique=True, db_index=True)

    # Dates
    created_date = models.DateTimeField(null=True, blank=True, db_index=True)
    modified_date = models.DateTimeField(null=True, blank=True)
    invoice_date = models.DateTimeField(null=True, blank=True, db_index=True, help_text="Invoice date")
    cancellation_date = models.DateTimeField(null=True, blank=True, help_text="Read-only")

    # Users
    created_by = models.IntegerField(null=True, blank=True)
    processed_by = models.IntegerField(null=True, blank=True)

    # Status & Workflow
    status = models.CharField(max_length=50, blank=True, db_index=True, help_text="Read-only order status")
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES, default='New', db_index=True)
    is_approved = models.BooleanField(default=True)
    is_void = models.BooleanField(default=False, help_text="Set true to void order")

    # Customer Information
    customer = models.ForeignKey(
        Contact, on_delete=models.PROTECT, related_name='sales_orders',
        null=True, blank=True, limit_choices_to={'type': 'Customer'}
    )
    customer_name = models.CharField(max_length=255, blank=True, help_text="Customer name from order")
    first_name = models.CharField(max_length=250, blank=True)
    last_name = models.CharField(max_length=250, blank=True)
    company = models.CharField(max_length=250, blank=True)
    email = models.EmailField(max_length=250, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    member_id = models.IntegerField(null=True, blank=True, help_text="Customer ID")
    member_email = models.EmailField(max_length=250, blank=True)

    # Delivery Address
    delivery_first_name = models.CharField(max_length=250, blank=True)
    delivery_last_name = models.CharField(max_length=250, blank=True)
    delivery_company = models.CharField(max_length=250, blank=True)
    delivery_address_1 = models.CharField(max_length=250, blank=True)
    delivery_address_2 = models.CharField(max_length=250, blank=True)
    delivery_city = models.CharField(max_length=250, blank=True)
    delivery_state = models.CharField(max_length=250, blank=True)
    delivery_postal_code = models.CharField(max_length=250, blank=True)
    delivery_country = models.CharField(max_length=250, blank=True)

    # Billing Address
    billing_first_name = models.CharField(max_length=250, blank=True)
    billing_last_name = models.CharField(max_length=250, blank=True)
    billing_company = models.CharField(max_length=250, blank=True)
    billing_address_1 = models.CharField(max_length=250, blank=True)
    billing_address_2 = models.CharField(max_length=250, blank=True)
    billing_city = models.CharField(max_length=250, blank=True)
    billing_state = models.CharField(max_length=250, blank=True)
    billing_postal_code = models.CharField(max_length=250, blank=True)
    billing_country = models.CharField(max_length=250, blank=True)

    # Financial - Totals
    product_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    freight_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    surcharge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_index=True)

    # Tax
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    tax_status = models.CharField(max_length=10, choices=TAX_STATUS_CHOICES, default='Incl')
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Currency
    currency = models.CharField(max_length=3, default='USD')
    currency_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)

    # Payment
    payment_method = models.CharField(max_length=100, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)

    # Branch & Shipping
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='sales_orders', null=True, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)

    # Notes & Comments
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    # Accounting
    accounting_integration_id = models.JSONField(default=dict, blank=True)

    # Metadata
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = SalesOrderManager()

    class Meta:
        db_table = 'cin7_sync_salesorder'
        ordering = ['-created_date']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['reference']),
            models.Index(fields=['created_date']),
            models.Index(fields=['status']),
            models.Index(fields=['stage']),
            models.Index(fields=['total']),
            models.Index(fields=['customer']),
        ]

    def __str__(self):
        return f"{self.reference} - {self.company or self.full_name}"

    @property
    def full_name(self):
        """Get customer full name"""
        return f"{self.first_name} {self.last_name}".strip()

    def mark_synced(self):
        """Mark order as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])


# ==================== SALES ORDER LINE ITEM ====================

class SalesOrderLineItemManager(models.Manager):
    """Custom manager for SalesOrderLineItem"""

    def get_for_order(self, sales_order_cin7_id):
        """Get all line items for a sales order"""
        return self.filter(cin7_sales_order_id=sales_order_cin7_id)


class SalesOrderLineItem(TimestampedModel):
    """
    Sales order line items from Cin7
    Individual products/items on a sales order
    """

    # Core Identifiers
    cin7_line_id = models.CharField(max_length=100, db_index=True, help_text="Cin7 line item ID")
    cin7_sales_order_id = models.CharField(max_length=100, db_index=True, help_text="Cin7 sales order ID")

    # Relations
    sales_order = models.ForeignKey(
        SalesOrder, on_delete=models.CASCADE, related_name='line_items',
        null=True, blank=True
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='sales_line_items',
        null=True, blank=True
    )

    # Product Identifiers (denormalized)
    cin7_product_id = models.IntegerField(null=True, blank=True, db_index=True)
    cin7_product_option_id = models.IntegerField(null=True, blank=True)
    code = models.CharField(max_length=100, db_index=True, help_text="SKU/Product code")
    name = models.CharField(max_length=255)
    barcode = models.CharField(max_length=100)

    # Variant Options
    option1 = models.CharField(max_length=100)
    option2 = models.CharField(max_length=100)
    option3 = models.CharField(max_length=100)

    # Quantities
    qty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    qty_shipped = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Pricing
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, db_index=True)

    # Additional Info
    comments = models.TextField(blank=True)
    sort_order = models.IntegerField(null=True, blank=True)
    line_type = models.CharField(max_length=50)

    # Raw Data
    raw_data = models.JSONField(default=dict, blank=True)

    objects = SalesOrderLineItemManager()

    class Meta:
        db_table = 'cin7_sync_salesorderlineitem'
        ordering = ['cin7_sales_order_id', 'sort_order']
        indexes = [
            models.Index(fields=['cin7_line_id']),
            models.Index(fields=['cin7_sales_order_id']),
            models.Index(fields=['cin7_product_id']),
            models.Index(fields=['code']),
            models.Index(fields=['line_total']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name} (Qty: {self.qty})"


# ==================== PURCHASE ORDER ====================

class PurchaseOrderManager(models.Manager):
    """Custom manager for PurchaseOrder"""

    def get_by_status(self, status):
        """Get orders by status"""
        return self.filter(status=status)

    def get_by_stage(self, stage):
        """Get orders by stage"""
        return self.filter(stage=stage)


class PurchaseOrder(TimestampedModel):
    """
    Purchase orders from Cin7 - Complete field coverage
    Based on https://api.cin7.com/api/Help/Api/GET-v1-PurchaseOrders_fields_where_order_page_rows
    """

    STAGE_CHOICES = [
        ('Draft', 'Draft'),
        ('Pending', 'Pending'),
        ('Ordered', 'Ordered'),
        ('Partial', 'Partially Received'),
        ('Received', 'Received'),
        ('Cancelled', 'Cancelled'),
    ]

    TAX_STATUS_CHOICES = [
        ('Incl', 'Tax Inclusive'),
        ('Excl', 'Tax Exclusive'),
        ('Exempt', 'Tax Exempt'),
    ]

    # Core Identifiers
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 purchase order ID")
    reference = models.CharField(max_length=30, unique=True, db_index=True)

    # Dates
    created_date = models.DateTimeField(null=True, blank=True, db_index=True)
    modified_date = models.DateTimeField(null=True, blank=True)
    order_date = models.DateTimeField(null=True, blank=True)
    expected_date = models.DateTimeField(null=True, blank=True)
    received_date = models.DateTimeField(null=True, blank=True)

    # Users
    created_by = models.IntegerField(null=True, blank=True)
    processed_by = models.IntegerField(null=True, blank=True)

    # Status & Workflow
    status = models.CharField(max_length=50, blank=True, db_index=True)
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES, default='Draft', db_index=True)
    is_approved = models.BooleanField(default=True)
    is_void = models.BooleanField(default=False)

    # Supplier Information
    supplier = models.ForeignKey(
        Contact, on_delete=models.PROTECT, related_name='purchase_orders',
        null=True, blank=True, limit_choices_to={'type': 'Supplier'}
    )
    first_name = models.CharField(max_length=250, blank=True)
    last_name = models.CharField(max_length=250, blank=True)
    company = models.CharField(max_length=250, blank=True)
    email = models.EmailField(max_length=250, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    member_id = models.IntegerField(null=True, blank=True)
    member_email = models.EmailField(max_length=250, blank=True)

    # Delivery Address
    delivery_first_name = models.CharField(max_length=250, blank=True)
    delivery_last_name = models.CharField(max_length=250, blank=True)
    delivery_company = models.CharField(max_length=250, blank=True)
    delivery_address_1 = models.CharField(max_length=250, blank=True)
    delivery_address_2 = models.CharField(max_length=250, blank=True)
    delivery_city = models.CharField(max_length=250, blank=True)
    delivery_state = models.CharField(max_length=250, blank=True)
    delivery_postal_code = models.CharField(max_length=250, blank=True)
    delivery_country = models.CharField(max_length=250, blank=True)

    # Billing Address
    billing_first_name = models.CharField(max_length=250, blank=True)
    billing_last_name = models.CharField(max_length=250, blank=True)
    billing_company = models.CharField(max_length=250, blank=True)
    billing_address_1 = models.CharField(max_length=250, blank=True)
    billing_address_2 = models.CharField(max_length=250, blank=True)
    billing_city = models.CharField(max_length=250, blank=True)
    billing_state = models.CharField(max_length=250, blank=True)
    billing_postal_code = models.CharField(max_length=250, blank=True)
    billing_country = models.CharField(max_length=250, blank=True)

    # Financial
    product_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    freight_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    surcharge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_index=True)

    # Tax
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    tax_status = models.CharField(max_length=10, choices=TAX_STATUS_CHOICES, default='Excl')
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Currency
    currency = models.CharField(max_length=3, default='USD')
    currency_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)

    # Branch
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='purchase_orders', null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)

    # Accounting
    accounting_integration_id = models.JSONField(default=dict, blank=True)

    # Metadata
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = PurchaseOrderManager()

    class Meta:
        db_table = 'cin7_sync_purchaseorder'
        ordering = ['-created_date']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['reference']),
            models.Index(fields=['created_date']),
            models.Index(fields=['status']),
            models.Index(fields=['stage']),
            models.Index(fields=['total']),
            models.Index(fields=['supplier']),
        ]

    def __str__(self):
        return f"{self.reference} - {self.company}"

    def mark_synced(self):
        """Mark order as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])


# ==================== STOCK ====================

class StockManager(models.Manager):
    """Custom manager for Stock"""

    def get_low_stock(self, threshold=10):
        """Get stock below threshold"""
        return self.filter(available__lt=threshold)

    def get_by_branch(self, branch):
        """Get stock for specific branch"""
        return self.filter(branch=branch)


class Stock(TimestampedModel):
    """
    Stock/inventory levels from Cin7 - Complete field coverage
    Based on https://api.cin7.com/api/Help/Api/GET-v1-Stock_fields_where_order_page_rows
    """

    # Relations
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_levels', null=True, blank=True)
    product_option = models.ForeignKey(ProductOption, on_delete=models.CASCADE, related_name='stock_levels', null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='stock_levels', null=True, blank=True)

    # Identifiers (denormalized from Cin7)
    cin7_product_id = models.IntegerField(db_index=True, help_text="Cin7 product ID")
    cin7_product_option_id = models.IntegerField(db_index=True, help_text="Product option ID")
    cin7_branch_id = models.IntegerField(db_index=True, help_text="Cin7 branch ID")
    branch_name = models.CharField(max_length=255, blank=True)

    # Product Info (denormalized for quick lookup)
    style_code = models.CharField(max_length=100, blank=True, db_index=True)
    code = models.CharField(max_length=100, blank=True, db_index=True, help_text="SKU")
    barcode = models.CharField(max_length=100, blank=True, db_index=True)
    product_name = models.CharField(max_length=250, blank=True)

    # Variant Attributes
    option_1 = models.CharField(max_length=50, blank=True)
    option_2 = models.CharField(max_length=50, blank=True)
    option_3 = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)

    # Stock Quantities
    available = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, db_index=True,
        help_text="Available to Sell (StockOnHand - OpenSales)"
    )
    stock_on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="SOH")
    open_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Allocated to orders")
    incoming = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Inbound PO quantity")
    virtual = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="For kit products")
    holding = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Holding stock")

    # Dates
    modified_date = models.DateTimeField(null=True, blank=True, help_text="Last transaction date")

    # Metadata
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = StockManager()

    class Meta:
        db_table = 'cin7_sync_stock'
        unique_together = [['cin7_product_option_id', 'cin7_branch_id']]
        ordering = ['product_name', 'code', 'branch_name']
        indexes = [
            models.Index(fields=['cin7_product_id']),
            models.Index(fields=['cin7_product_option_id']),
            models.Index(fields=['cin7_branch_id']),
            models.Index(fields=['code']),
            models.Index(fields=['barcode']),
            models.Index(fields=['available']),
            models.Index(fields=['cin7_product_option_id', 'cin7_branch_id']),
        ]

    def __str__(self):
        return f"{self.code} @ {self.branch_name}: {self.available} available"

    @property
    def is_low_stock(self):
        """Check if stock is low (less than 10)"""
        return self.available < 10

    def mark_synced(self):
        """Mark stock as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])
