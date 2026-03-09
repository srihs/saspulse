from django.core.management.base import BaseCommand
from django.db import connection
from dashboard.models import StoreReplenishmentRequestBatch, StoreReplenishmentRequestItem


class Command(BaseCommand):
    help = 'Delete all replenishment requests and reset ID sequences'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\n' + '='*70))
        self.stdout.write(self.style.WARNING('REPLENISHMENT REQUEST CLEANUP'))
        self.stdout.write(self.style.WARNING('='*70 + '\n'))

        # Count before deletion
        batch_count = StoreReplenishmentRequestBatch.objects.count()
        item_count = StoreReplenishmentRequestItem.objects.count()

        self.stdout.write(f'Current state:')
        self.stdout.write(f'  - Batches: {batch_count}')
        self.stdout.write(f'  - Items: {item_count}\n')

        if batch_count == 0 and item_count == 0:
            self.stdout.write(self.style.SUCCESS('Tables are already empty. Resetting sequences...\n'))
        else:
            self.stdout.write(self.style.WARNING(f'Preparing to delete {item_count} items and {batch_count} batches...\n'))

        # Delete all items first (foreign key constraint)
        StoreReplenishmentRequestItem.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {item_count} items'))

        # Delete all batches
        StoreReplenishmentRequestBatch.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {batch_count} batches\n'))

        # Reset auto-increment sequences (MySQL syntax)
        with connection.cursor() as cursor:
            # Get table names
            item_table = StoreReplenishmentRequestItem._meta.db_table
            batch_table = StoreReplenishmentRequestBatch._meta.db_table

            self.stdout.write(f'Resetting AUTO_INCREMENT for:')
            self.stdout.write(f'  - Items table: {item_table}')
            self.stdout.write(f'  - Batches table: {batch_table}\n')

            # Reset AUTO_INCREMENT for items table
            cursor.execute(f"ALTER TABLE {item_table} AUTO_INCREMENT = 1;")
            self.stdout.write(self.style.SUCCESS(f'✓ Reset {item_table} AUTO_INCREMENT to 1'))

            # Reset AUTO_INCREMENT for batches table
            cursor.execute(f"ALTER TABLE {batch_table} AUTO_INCREMENT = 1;")
            self.stdout.write(self.style.SUCCESS(f'✓ Reset {batch_table} AUTO_INCREMENT to 1\n'))

        # Verify cleanup
        remaining_batches = StoreReplenishmentRequestBatch.objects.count()
        remaining_items = StoreReplenishmentRequestItem.objects.count()

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('CLEANUP COMPLETE'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f'\nVerification:')
        self.stdout.write(f'  - Remaining batches: {remaining_batches}')
        self.stdout.write(f'  - Remaining items: {remaining_items}')
        self.stdout.write(f'  - Next batch ID: 1')
        self.stdout.write(f'  - Next item ID: 1\n')

        if remaining_batches == 0 and remaining_items == 0:
            self.stdout.write(self.style.SUCCESS('SUCCESS: All replenishment requests deleted and IDs reset!\n'))
        else:
            self.stdout.write(self.style.ERROR(f'WARNING: {remaining_batches + remaining_items} records still remain!\n'))
