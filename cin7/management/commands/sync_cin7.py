"""
Django management command to sync data from Cin7 - COMPREHENSIVE VERSION

Syncs ALL available fields from Cin7 API to local database.

Usage:
    python3 manage.py sync_cin7 --help
    python3 manage.py sync_cin7 --entity branches
    python3 manage.py sync_cin7 --entity products --limit 100
    python3 manage.py sync_cin7 --entity product_options
    python3 manage.py sync_cin7 --entity all --full-sync
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from cin7.client import Cin7Client, Cin7APIError, Cin7AuthenticationError
from cin7.models import (
    Branch, Product, ProductOption, ProductCategory, Contact,
    SalesOrder, PurchaseOrder, Stock
)


class Command(BaseCommand):
    help = 'Sync data from Cin7 API to local database (comprehensive field coverage)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--entity',
            type=str,
            default='all',
            choices=['all', 'branches', 'products', 'product_options', 'contacts', 'stock', 'sales_orders', 'purchase_orders'],
            help='Which entity to sync (default: all)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=250,
            help='Maximum number of records to sync per request (default: 250)'
        )
        parser.add_argument(
            '--full-sync',
            action='store_true',
            help='Perform full sync (fetch all pages)'
        )

    def handle(self, *args, **options):
        entity = options['entity']
        limit = options['limit']
        full_sync = options['full_sync']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Cin7 Data Sync - Comprehensive'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        try:
            # Initialize Cin7 client
            self.stdout.write('\nInitializing Cin7 client...')
            client = Cin7Client()
            self.stdout.write(self.style.SUCCESS(f'✓ Connected to {client.base_url}'))

            # Sync entities based on selection
            if entity == 'all':
                self.sync_branches(client, limit)
                self.sync_products(client, limit, full_sync)
                self.sync_product_options(client, limit, full_sync)
                self.sync_contacts(client, limit, full_sync)
                self.sync_stock(client, limit, full_sync)
                self.sync_sales_orders(client, limit, full_sync)
                self.sync_purchase_orders(client, limit, full_sync)
            elif entity == 'branches':
                self.sync_branches(client, limit)
            elif entity == 'products':
                self.sync_products(client, limit, full_sync)
            elif entity == 'product_options':
                self.sync_product_options(client, limit, full_sync)
            elif entity == 'contacts':
                self.sync_contacts(client, limit, full_sync)
            elif entity == 'stock':
                self.sync_stock(client, limit, full_sync)
            elif entity == 'sales_orders':
                self.sync_sales_orders(client, limit, full_sync)
            elif entity == 'purchase_orders':
                self.sync_purchase_orders(client, limit, full_sync)

            # Close client
            client.close()

            self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
            self.stdout.write(self.style.SUCCESS('Sync completed successfully!'))
            self.stdout.write(self.style.SUCCESS('=' * 60))

        except Cin7AuthenticationError as e:
            raise CommandError(f'Authentication failed: {e}')
        except Cin7APIError as e:
            raise CommandError(f'API error: {e}')
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'Unexpected error: {e}'))
            self.stdout.write(traceback.format_exc())
            raise CommandError(f'Unexpected error: {e}')

    def sync_branches(self, client, limit):
        """Sync branches from Cin7 - All fields"""
        self.stdout.write('\n--- Syncing Branches ---')

        try:
            branches_data = client.get_branches()
            self.stdout.write(f'Fetched {len(branches_data)} branches from Cin7')

            created_count = 0
            updated_count = 0

            for branch_data in branches_data:
                cin7_id = branch_data.get('id')
                defaults = {
                    'name': branch_data.get('name', ''),
                    'code': branch_data.get('code', f'BRANCH-{cin7_id}'),
                    'address': branch_data.get('address', ''),
                    'city': branch_data.get('city', ''),
                    'state': branch_data.get('state', ''),
                    'country': branch_data.get('country', ''),
                    'postal_code': branch_data.get('postalCode', ''),
                    'is_active': branch_data.get('isActive', True),
                }

                branch, created = Branch.objects.update_or_create(
                    cin7_id=cin7_id,
                    defaults=defaults
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            self.stdout.write(self.style.SUCCESS(
                f'✓ Branches: {created_count} created, {updated_count} updated'
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error syncing branches: {e}'))

    def sync_products(self, client, limit, full_sync=False):
        """Sync products from Cin7 - ALL fields"""
        self.stdout.write('\n--- Syncing Products ---')

        try:
            page = 1
            total_created = 0
            total_updated = 0

            while True:
                self.stdout.write(f'Fetching page {page}...')
                products_data = client.get_products(page=page, rows=limit)

                if not products_data:
                    break

                self.stdout.write(f'Processing {len(products_data)} products...')

                for product_data in products_data:
                    cin7_id = product_data.get('id')

                    defaults = {
                        # Core
                        'style_code': product_data.get('styleCode', ''),
                        'name': product_data.get('name', ''),

                        # Status & Dates
                        'status': product_data.get('status', 'Public'),
                        'cin7_created_date': self.parse_date(product_data.get('createdDate')),
                        'cin7_modified_date': self.parse_date(product_data.get('modifiedDate')),

                        # Description
                        'description': product_data.get('description', ''),
                        'tags': product_data.get('tags', ''),

                        # Classification
                        'brand': product_data.get('brand', ''),
                        'category': product_data.get('category', ''),
                        'sub_category': product_data.get('subCategory', ''),
                        'category_id_array': product_data.get('categoryIdArray', []),

                        # Supplier
                        'supplier_id': product_data.get('supplierId'),
                        'supplier_code': product_data.get('supplierCode', ''),

                        # Channels
                        'channels': product_data.get('channels', ''),

                        # Physical Dimensions
                        'weight': product_data.get('weight'),
                        'height': product_data.get('height'),
                        'width': product_data.get('width'),
                        'length': product_data.get('length'),
                        'volume': product_data.get('volume'),

                        # Inventory Control
                        'stock_control': product_data.get('stockControl', ''),
                        'order_type': product_data.get('orderType', 'Order'),
                        'product_type': product_data.get('productType', ''),
                        'product_subtype': product_data.get('productSubtype', ''),

                        # Project
                        'project_name': product_data.get('projectName', ''),

                        # Options Configuration
                        'option_label_1': product_data.get('optionLabel1', ''),
                        'option_label_2': product_data.get('optionLabel2', ''),
                        'option_label_3': product_data.get('optionLabel3', ''),

                        # Accounting
                        'sales_account': product_data.get('salesAccount', ''),
                        'purchases_account': product_data.get('purchasesAccount', ''),
                        'import_customs_duty': product_data.get('importCustomsDuty'),

                        # Size Range
                        'size_range_id': product_data.get('sizeRangeId'),

                        # Custom Fields & Media
                        'custom_fields': product_data.get('customFields', {}),
                        'images': product_data.get('images', []),
                        'pdf_upload': product_data.get('pdfUpload', ''),
                        'pdf_description': product_data.get('pdfDescription', ''),

                        # Metadata
                        'last_synced_at': timezone.now(),
                    }

                    product, created = Product.objects.update_or_create(
                        cin7_id=cin7_id,
                        defaults=defaults
                    )

                    if created:
                        total_created += 1
                    else:
                        total_updated += 1

                    # Sync product options if present
                    if 'productOptions' in product_data and product_data['productOptions']:
                        self.sync_product_options_for_product(product, product_data['productOptions'])

                if not full_sync or len(products_data) < limit:
                    break

                page += 1

            self.stdout.write(self.style.SUCCESS(
                f'✓ Products: {total_created} created, {total_updated} updated'
            ))

        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'✗ Error syncing products: {e}'))
            self.stdout.write(traceback.format_exc())

    def sync_product_options_for_product(self, product, options_data):
        """Sync product options for a specific product"""
        for option_data in options_data:
            cin7_id = option_data.get('id')
            if not cin7_id:
                continue

            defaults = {
                'product': product,
                'code': option_data.get('code', f'OPT-{cin7_id}'),
                'barcode': option_data.get('barcode', ''),
                'supplier_code': option_data.get('supplierCode', ''),
                'status': option_data.get('status', 'Public'),
                'cin7_created_date': self.parse_date(option_data.get('createdDate')),
                'cin7_modified_date': self.parse_date(option_data.get('modifiedDate')),
                'option_1': option_data.get('option1', ''),
                'option_2': option_data.get('option2', ''),
                'option_3': option_data.get('option3', ''),
                'size': option_data.get('size', ''),
                'size_id': option_data.get('sizeId'),
                'retail_price': option_data.get('retailPrice', 0),
                'wholesale_price': option_data.get('wholesalePrice', 0),
                'vip_price': option_data.get('vipPrice', 0),
                'special_price': option_data.get('specialPrice'),
                'specials_start_date': self.parse_date(option_data.get('specialsStartDate'), date_only=True),
                'special_days': option_data.get('specialDays'),
                'cost_price': option_data.get('costPrice', 0),
                'stock_available': option_data.get('stockAvailable', 0),
                'stock_on_hand': option_data.get('stockOnHand', 0),
                'option_weight': option_data.get('optionWeight'),
                'image': option_data.get('image', ''),
                'uom_options': option_data.get('uomOptions', []),
                'price_columns': option_data.get('priceColumns', {}),
                'last_synced_at': timezone.now(),
            }

            ProductOption.objects.update_or_create(
                cin7_id=cin7_id,
                defaults=defaults
            )

    def sync_product_options(self, client, limit, full_sync=False):
        """Sync product options from Cin7 - ALL fields"""
        self.stdout.write('\n--- Syncing Product Options ---')
        self.stdout.write(self.style.WARNING('Product options are synced with products'))

    def sync_contacts(self, client, limit, full_sync=False):
        """Sync contacts from Cin7 - ALL fields"""
        self.stdout.write('\n--- Syncing Contacts ---')

        try:
            page = 1
            total_created = 0
            total_updated = 0

            while True:
                self.stdout.write(f'Fetching page {page}...')
                contacts_data = client.get_contacts(page=page, rows=limit)

                if not contacts_data:
                    break

                self.stdout.write(f'Processing {len(contacts_data)} contacts...')

                for contact_data in contacts_data:
                    cin7_id = contact_data.get('id')

                    # Determine contact type from Cin7 API
                    contact_type_from_api = contact_data.get('type', 'Customer')

                    defaults = {
                        # Core
                        'type': contact_type_from_api,

                        # Status & Dates
                        'is_active': contact_data.get('isActive', True),
                        'cin7_created_date': self.parse_date(contact_data.get('createdDate')),
                        'cin7_modified_date': self.parse_date(contact_data.get('modifiedDate')),

                        # Personal Information
                        'company': contact_data.get('company', ''),
                        'first_name': contact_data.get('firstName', ''),
                        'last_name': contact_data.get('lastName', ''),
                        'job_title': contact_data.get('jobTitle', ''),

                        # Contact Details
                        'email': contact_data.get('email', ''),
                        'website': contact_data.get('website', ''),
                        'phone': contact_data.get('phone', ''),
                        'fax': contact_data.get('fax', ''),
                        'mobile': contact_data.get('mobile', ''),

                        # Business Information
                        'sales_person_id': contact_data.get('salesPersonId'),
                        'account_number': contact_data.get('accountNumber', ''),

                        # Billing Information
                        'billing_id': contact_data.get('billingId'),
                        'billing_company': contact_data.get('billingCompany', ''),
                        'accounts_first_name': contact_data.get('accountsFirstName', ''),
                        'accounts_last_name': contact_data.get('accountsLastName', ''),
                        'billing_email': contact_data.get('billingEmail', ''),
                        'accounts_phone': contact_data.get('accountsPhone', ''),
                        'billing_cost_center': contact_data.get('billingCostCenter', ''),
                        'cost_center': contact_data.get('costCenter', ''),

                        # Pricing & Discounts
                        'price_column': contact_data.get('priceColumn', ''),
                        'percentage_off': contact_data.get('percentageOff'),

                        # Financial Terms
                        'payment_terms': contact_data.get('paymentTerms', ''),
                        'tax_status': contact_data.get('taxStatus', ''),
                        'tax_number': contact_data.get('taxNumber', ''),
                        'credit_limit': contact_data.get('creditLimit', 0),
                        'balance_owing': contact_data.get('balanceOwing', 0),
                        'on_hold': contact_data.get('onHold', False),

                        # Classification
                        'group': contact_data.get('group', ''),
                        'sub_group': contact_data.get('subGroup', ''),
                        'stages': contact_data.get('stages', ''),

                        # Accounting Integration
                        'accounting_integration_id': contact_data.get('accountingIntegrationId', {}),

                        # Address Fields
                        'address_line_1': contact_data.get('addressLine1', ''),
                        'address_line_2': contact_data.get('addressLine2', ''),
                        'city': contact_data.get('city', ''),
                        'state': contact_data.get('state', ''),
                        'postal_code': contact_data.get('postalCode', ''),
                        'country': contact_data.get('country', ''),

                        # Delivery Address
                        'delivery_first_name': contact_data.get('deliveryFirstName', ''),
                        'delivery_last_name': contact_data.get('deliveryLastName', ''),
                        'delivery_company': contact_data.get('deliveryCompany', ''),
                        'delivery_address_1': contact_data.get('deliveryAddress1', ''),
                        'delivery_address_2': contact_data.get('deliveryAddress2', ''),
                        'delivery_city': contact_data.get('deliveryCity', ''),
                        'delivery_state': contact_data.get('deliveryState', ''),
                        'delivery_postal_code': contact_data.get('deliveryPostalCode', ''),
                        'delivery_country': contact_data.get('deliveryCountry', ''),

                        # Billing Address
                        'billing_first_name': contact_data.get('billingFirstName', ''),
                        'billing_last_name': contact_data.get('billingLastName', ''),
                        'billing_address_1': contact_data.get('billingAddress1', ''),
                        'billing_address_2': contact_data.get('billingAddress2', ''),
                        'billing_city': contact_data.get('billingCity', ''),
                        'billing_state': contact_data.get('billingState', ''),
                        'billing_postal_code': contact_data.get('billingPostalCode', ''),
                        'billing_country': contact_data.get('billingCountry', ''),

                        # Comments
                        'comments': contact_data.get('comments', ''),

                        # Metadata
                        'last_synced_at': timezone.now(),
                    }

                    contact, created = Contact.objects.update_or_create(
                        cin7_id=cin7_id,
                        defaults=defaults
                    )

                    if created:
                        total_created += 1
                    else:
                        total_updated += 1

                if not full_sync or len(contacts_data) < limit:
                    break

                page += 1

            self.stdout.write(self.style.SUCCESS(
                f'✓ Contacts: {total_created} created, {total_updated} updated'
            ))

        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'✗ Error syncing contacts: {e}'))
            self.stdout.write(traceback.format_exc())

    def sync_stock(self, client, limit, full_sync=False):
        """Sync stock levels from Cin7 - ALL fields"""
        self.stdout.write('\n--- Syncing Stock ---')

        try:
            page = 1
            total_created = 0
            total_updated = 0

            while True:
                self.stdout.write(f'Fetching page {page}...')
                stock_data_list = client.get_stock(page=page, rows=limit)

                if not stock_data_list:
                    break

                self.stdout.write(f'Processing {len(stock_data_list)} stock records...')

                for stock_data in stock_data_list:
                    cin7_product_option_id = stock_data.get('productOptionId')
                    cin7_branch_id = stock_data.get('branchId')

                    if not cin7_product_option_id or not cin7_branch_id:
                        continue

                    # Try to link to existing product/option/branch
                    product = Product.objects.filter(cin7_id=stock_data.get('productId')).first()
                    product_option = ProductOption.objects.filter(cin7_id=cin7_product_option_id).first()
                    branch = Branch.objects.filter(cin7_id=cin7_branch_id).first()

                    defaults = {
                        'product': product,
                        'product_option': product_option,
                        'branch': branch,
                        'cin7_product_id': stock_data.get('productId', 0),
                        'cin7_product_option_id': cin7_product_option_id,
                        'cin7_branch_id': cin7_branch_id,
                        'branch_name': stock_data.get('branchName', ''),
                        'style_code': stock_data.get('styleCode', ''),
                        'code': stock_data.get('code', ''),
                        'barcode': stock_data.get('barcode', ''),
                        'product_name': stock_data.get('productName', ''),
                        'option_1': stock_data.get('option1', ''),
                        'option_2': stock_data.get('option2', ''),
                        'option_3': stock_data.get('option3', ''),
                        'size': stock_data.get('size', ''),
                        'available': stock_data.get('available', 0),
                        'stock_on_hand': stock_data.get('stockOnHand', 0),
                        'open_sales': stock_data.get('openSales', 0),
                        'incoming': stock_data.get('incoming', 0),
                        'virtual': stock_data.get('virtual', 0),
                        'holding': stock_data.get('holding', 0),
                        'modified_date': self.parse_date(stock_data.get('modifiedDate')),
                        'last_synced_at': timezone.now(),
                    }

                    stock, created = Stock.objects.update_or_create(
                        cin7_product_option_id=cin7_product_option_id,
                        cin7_branch_id=cin7_branch_id,
                        defaults=defaults
                    )

                    if created:
                        total_created += 1
                    else:
                        total_updated += 1

                if not full_sync or len(stock_data_list) < limit:
                    break

                page += 1

            self.stdout.write(self.style.SUCCESS(
                f'✓ Stock: {total_created} created, {total_updated} updated'
            ))

        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'✗ Error syncing stock: {e}'))
            self.stdout.write(traceback.format_exc())

    def sync_sales_orders(self, client, limit, full_sync=False):
        """Sync sales orders from Cin7 - ALL fields"""
        self.stdout.write('\n--- Syncing Sales Orders ---')
        self.stdout.write(self.style.WARNING('Sales orders sync implementation pending'))
        # TODO: Implement comprehensive sales orders sync

    def sync_purchase_orders(self, client, limit, full_sync=False):
        """Sync purchase orders from Cin7 - ALL fields"""
        self.stdout.write('\n--- Syncing Purchase Orders ---')
        self.stdout.write(self.style.WARNING('Purchase orders sync implementation pending'))
        # TODO: Implement comprehensive purchase orders sync

    def parse_date(self, date_string, date_only=False):
        """Parse date string from Cin7 API"""
        if not date_string:
            return None
        try:
            dt = parse_datetime(date_string)
            if date_only and dt:
                return dt.date()
            return dt
        except (ValueError, AttributeError):
            return None
