"""
Cin7 Django Models

Models representing Cin7 entities:
- Product: Products/inventory items
- ProductCategory: Product categories
- Branch: Warehouses/locations
- Contact: Customers and suppliers
- SalesOrder: Sales orders
- PurchaseOrder: Purchase orders
- Stock: Inventory/stock levels per branch
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class TimestampedModel(models.Model):
    """Abstract base model with created/updated timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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
        verbose_name_plural = "Product Categories"
        ordering = ['name']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name


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
        verbose_name_plural = "Branches"
        ordering = ['name']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class ProductManager(models.Manager):
    """Custom manager for Product"""

    def get_active(self):
        """Get all active products"""
        return self.filter(is_active=True)

    def get_low_stock(self, threshold=10):
        """Get products with stock below threshold"""
        return self.filter(stock_quantity__lt=threshold, is_active=True)

    def get_by_brand(self, brand):
        """Get products by brand"""
        return self.filter(brand__iexact=brand, is_active=True)


class Product(TimestampedModel):
    """Products from Cin7"""

    # Cin7 fields
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 product ID")
    code = models.CharField(max_length=100, unique=True, db_index=True, help_text="SKU/Product code")
    name = models.CharField(max_length=255, db_index=True)
    style_code = models.CharField(max_length=100, blank=True, db_index=True)
    description = models.TextField(blank=True)

    # Categorization
    brand = models.CharField(max_length=100, blank=True, db_index=True)
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )

    # Pricing
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    sell_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3, default='USD')

    # Inventory
    stock_quantity = models.IntegerField(default=0, help_text="Total stock across all branches")
    min_stock_level = models.IntegerField(default=0, help_text="Minimum stock level before reorder")
    max_stock_level = models.IntegerField(default=0, help_text="Maximum stock level")

    # Physical properties
    barcode = models.CharField(max_length=100, blank=True, db_index=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    weight_unit = models.CharField(max_length=10, default='kg')

    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    is_sellable = models.BooleanField(default=True)
    is_purchasable = models.BooleanField(default=True)

    # Metadata
    cin7_created_date = models.DateTimeField(null=True, blank=True)
    cin7_modified_date = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = ProductManager()

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['code']),
            models.Index(fields=['name']),
            models.Index(fields=['brand']),
            models.Index(fields=['barcode']),
            models.Index(fields=['is_active']),
            models.Index(fields=['stock_quantity']),
            models.Index(fields=['last_synced_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def is_low_stock(self):
        """Check if product is below minimum stock level"""
        return self.stock_quantity < self.min_stock_level

    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.cost_price == 0:
            return 0
        return ((self.sell_price - self.cost_price) / self.cost_price) * 100

    def mark_synced(self):
        """Mark product as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])


class ContactManager(models.Manager):
    """Custom manager for Contact"""

    def get_customers(self):
        """Get all customers"""
        return self.filter(is_customer=True, is_active=True)

    def get_suppliers(self):
        """Get all suppliers"""
        return self.filter(is_supplier=True, is_active=True)


class Contact(TimestampedModel):
    """Customers and suppliers from Cin7"""

    CONTACT_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('supplier', 'Supplier'),
        ('both', 'Both'),
    ]

    # Cin7 fields
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 contact ID")
    code = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    company_name = models.CharField(max_length=255, blank=True)

    # Contact type
    contact_type = models.CharField(max_length=10, choices=CONTACT_TYPE_CHOICES, default='customer')
    is_customer = models.BooleanField(default=False, db_index=True)
    is_supplier = models.BooleanField(default=False, db_index=True)

    # Contact information
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)

    # Address
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # Financial
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')

    # Status
    is_active = models.BooleanField(default=True, db_index=True)

    # Metadata
    cin7_created_date = models.DateTimeField(null=True, blank=True)
    cin7_modified_date = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = ContactManager()

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['code']),
            models.Index(fields=['name']),
            models.Index(fields=['is_customer']),
            models.Index(fields=['is_supplier']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def mark_synced(self):
        """Mark contact as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])


class SalesOrderManager(models.Manager):
    """Custom manager for SalesOrder"""

    def get_pending(self):
        """Get pending orders"""
        return self.filter(status='pending')

    def get_completed(self):
        """Get completed orders"""
        return self.filter(status='completed')

    def get_by_date_range(self, start_date, end_date):
        """Get orders within date range"""
        return self.filter(order_date__range=[start_date, end_date])


class SalesOrder(TimestampedModel):
    """Sales orders from Cin7"""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Cin7 fields
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 sales order ID")
    reference = models.CharField(max_length=100, unique=True, db_index=True)

    # Customer
    customer = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name='sales_orders',
        limit_choices_to={'is_customer': True}
    )

    # Branch
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name='sales_orders',
        null=True,
        blank=True
    )

    # Order details
    order_date = models.DateTimeField(db_index=True)
    required_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)

    # Financial
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0, db_index=True)
    currency = models.CharField(max_length=3, default='USD')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)

    # Notes
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    # Metadata
    cin7_created_date = models.DateTimeField(null=True, blank=True)
    cin7_modified_date = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = SalesOrderManager()

    class Meta:
        ordering = ['-order_date']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['reference']),
            models.Index(fields=['order_date']),
            models.Index(fields=['status']),
            models.Index(fields=['total']),
            models.Index(fields=['customer']),
        ]

    def __str__(self):
        return f"{self.reference} - {self.customer.name} ({self.total})"

    def mark_synced(self):
        """Mark order as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])


class PurchaseOrderManager(models.Manager):
    """Custom manager for PurchaseOrder"""

    def get_pending(self):
        """Get pending orders"""
        return self.filter(status='pending')

    def get_received(self):
        """Get received orders"""
        return self.filter(status='received')


class PurchaseOrder(TimestampedModel):
    """Purchase orders from Cin7"""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('ordered', 'Ordered'),
        ('partial', 'Partially Received'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]

    # Cin7 fields
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 purchase order ID")
    reference = models.CharField(max_length=100, unique=True, db_index=True)

    # Supplier
    supplier = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        limit_choices_to={'is_supplier': True}
    )

    # Branch
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        null=True,
        blank=True
    )

    # Order details
    order_date = models.DateTimeField(db_index=True)
    expected_date = models.DateTimeField(null=True, blank=True)
    received_date = models.DateTimeField(null=True, blank=True)

    # Financial
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0, db_index=True)
    currency = models.CharField(max_length=3, default='USD')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)

    # Notes
    notes = models.TextField(blank=True)

    # Metadata
    cin7_created_date = models.DateTimeField(null=True, blank=True)
    cin7_modified_date = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = PurchaseOrderManager()

    class Meta:
        ordering = ['-order_date']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['reference']),
            models.Index(fields=['order_date']),
            models.Index(fields=['status']),
            models.Index(fields=['total']),
            models.Index(fields=['supplier']),
        ]

    def __str__(self):
        return f"{self.reference} - {self.supplier.name} ({self.total})"

    def mark_synced(self):
        """Mark order as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])


class StockManager(models.Manager):
    """Custom manager for Stock"""

    def get_low_stock(self, threshold=10):
        """Get stock below threshold"""
        return self.filter(available_quantity__lt=threshold)

    def get_by_branch(self, branch):
        """Get stock for specific branch"""
        return self.filter(branch=branch)


class Stock(TimestampedModel):
    """Stock/inventory levels from Cin7"""

    # Cin7 fields
    cin7_id = models.IntegerField(unique=True, db_index=True, help_text="Cin7 stock ID")

    # Relations
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_levels'
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='stock_levels'
    )

    # Quantities
    available_quantity = models.IntegerField(default=0, db_index=True)
    allocated_quantity = models.IntegerField(default=0)
    on_order_quantity = models.IntegerField(default=0)
    total_quantity = models.IntegerField(default=0)

    # Metadata
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = StockManager()

    class Meta:
        unique_together = [['product', 'branch']]
        ordering = ['product', 'branch']
        indexes = [
            models.Index(fields=['cin7_id']),
            models.Index(fields=['product', 'branch']),
            models.Index(fields=['available_quantity']),
        ]

    def __str__(self):
        return f"{self.product.code} @ {self.branch.name}: {self.available_quantity}"

    @property
    def is_low_stock(self):
        """Check if stock is below product's minimum level"""
        return self.available_quantity < self.product.min_stock_level

    def mark_synced(self):
        """Mark stock as synced with Cin7"""
        self.last_synced_at = timezone.now()
        self.save(update_fields=['last_synced_at'])
