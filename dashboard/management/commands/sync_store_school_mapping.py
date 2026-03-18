"""
Management command to sync store-school mappings from product catalog

This command extracts unique store-school combinations from the cin7_sync_product table
where category_name ends with 'Store' or 'Shop' and creates/updates StoreSchoolMapping records.

Usage:
    python manage.py sync_store_school_mapping

Options:
    --clear     Delete all existing mappings before syncing
    --dry-run   Show what would be synced without making changes
"""

from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from dashboard.models import StoreSchoolMapping
from cin7.models import Product


class Command(BaseCommand):
    help = 'Sync store-school mappings from product catalog'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing mappings before syncing',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        clear = options['clear']

        self.stdout.write(self.style.SUCCESS('Starting store-school mapping sync...'))

        # Clear existing mappings if requested
        if clear and not dry_run:
            count = StoreSchoolMapping.objects.all().count()
            StoreSchoolMapping.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {count} existing mappings'))

        # Query products where category_name ends with 'Store' or 'Shop'
        self.stdout.write('Extracting store-school combinations from products...')
        stores = Product.objects.filter(
            Q(category_name__iendswith='Store') | Q(category_name__iendswith='Shop')
        ).exclude(
            category_name__in=['Store', 'Shop']
        ).exclude(
            category_name__istartswith='Wholesale'
        ).values('category_name', 'sub_category').annotate(
            product_count=Count('id')
        )

        total_found = stores.count()
        self.stdout.write(f'Found {total_found} unique store-school combinations')

        # Track statistics
        created_count = 0
        updated_count = 0
        skipped_count = 0

        # Process each store-school combination
        for store_data in stores:
            category_name = store_data['category_name']
            school_name = store_data['sub_category']
            product_count = store_data['product_count']

            # Skip if school_name is empty
            if not school_name or school_name.strip() == '':
                skipped_count += 1
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  SKIP: {category_name} (empty school name)'
                        )
                    )
                continue

            # Extract store name (remove ' Store' or ' Shop' suffix)
            store_name = category_name
            if store_name.endswith(' Store'):
                store_name = store_name[:-6]
            elif store_name.endswith(' Shop'):
                store_name = store_name[:-5]

            if dry_run:
                # Check if would be created or updated
                exists = StoreSchoolMapping.objects.filter(
                    category_name=category_name,
                    school_name=school_name
                ).exists()

                if exists:
                    self.stdout.write(
                        self.style.HTTP_INFO(
                            f'  UPDATE: {store_name} -> {school_name} ({product_count} products)'
                        )
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  CREATE: {store_name} -> {school_name} ({product_count} products)'
                        )
                    )
                    created_count += 1
            else:
                # Create or update mapping
                mapping, created = StoreSchoolMapping.objects.update_or_create(
                    category_name=category_name,
                    school_name=school_name,
                    defaults={
                        'store_name': store_name,
                        'product_count': product_count,
                        'is_active': True,
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  Created: {store_name} -> {school_name} ({product_count} products)'
                        )
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.HTTP_INFO(
                            f'  Updated: {store_name} -> {school_name} ({product_count} products)'
                        )
                    )

        # Print summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Sync Summary ==='))
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes made'))
        self.stdout.write(f'Total combinations found: {total_found}')
        self.stdout.write(self.style.SUCCESS(f'Would create/Created: {created_count}'))
        self.stdout.write(self.style.HTTP_INFO(f'Would update/Updated: {updated_count}'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'Skipped (empty school): {skipped_count}'))

        if dry_run:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'This was a dry run. Run without --dry-run to apply changes.'
                )
            )
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Sync completed successfully!'))
