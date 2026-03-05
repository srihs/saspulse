"""
Send email notifications for replenishment requests

This command sends automated emails to:
1. Store Managers - New replenishment requests for their review
2. Store Managers - Reminders for pending requests
3. DP Team - Batch of approved requests ready for review
4. DP Team - Urgent/critical stock alerts
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.core.mail import send_mail, send_mass_mail
from django.conf import settings
from django.db import connection
from dashboard.models import ReplenishmentRequest, ReplenishmentNotification
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Send email notifications for replenishment requests'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['store_new', 'store_reminder', 'dp_batch', 'dp_urgent', 'all'],
            default='all',
            help='Type of notification to send'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate without sending emails'
        )

    def handle(self, *args, **options):
        notification_type = options['type']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('=' * 80))
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No emails will be sent'))
            self.stdout.write(self.style.WARNING('=' * 80))

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('REPLENISHMENT NOTIFICATION SYSTEM'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        if notification_type in ['store_new', 'all']:
            self.send_store_new_requests(dry_run)

        if notification_type in ['store_reminder', 'all']:
            self.send_store_reminders(dry_run)

        if notification_type in ['dp_batch', 'all']:
            self.send_dp_batch_notification(dry_run)

        if notification_type in ['dp_urgent', 'all']:
            self.send_dp_urgent_alerts(dry_run)

        self.stdout.write(self.style.SUCCESS('\n✓ Notification process complete!'))

    def send_store_new_requests(self, dry_run=False):
        """
        Send emails to store managers about new pending requests
        """
        self.stdout.write('\n1. Sending notifications for NEW requests to store managers...')

        # Get pending requests grouped by branch
        # For now, we'll send to all admin users (later: filter by branch assignment)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    b.company as branch_name,
                    b.id as branch_id,
                    COUNT(*) as request_count,
                    SUM(CASE WHEN urgency = 'critical' THEN 1 ELSE 0 END) as critical_count,
                    SUM(suggested_quantity) as total_units
                FROM dashboard_replenishmentrequest rr
                JOIN cin7_sync_branch b ON b.id = rr.branch_id
                WHERE rr.status = 'pending'
                  AND rr.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                GROUP BY b.company, b.id
            """)

            branches = cursor.fetchall()

        if not branches:
            self.stdout.write('  No new requests found')
            return

        # Get store managers (for now, all staff users)
        store_managers = CustomUser.objects.filter(is_staff=True, is_active=True)

        sent_count = 0

        for branch_name, branch_id, count, critical, total_units in branches:
            subject = f"⚠️ {count} New Replenishment Requests for {branch_name}"

            message = f"""
Hello,

{count} new replenishment requests have been generated for {branch_name} based on AI sales forecasting.

Summary:
- Total Requests: {count}
- Critical Urgency: {critical}
- Total Units Needed: {int(total_units)}

Please review and approve/modify these requests in the replenishment dashboard:
{settings.SITE_URL}/dashboard/replenishment/store/

These recommendations are based on:
- 30-day sales forecasts from our AI model
- Current stock levels at your branch
- Historical sales patterns

Action Required:
Please review these requests by end of this week and approve/modify quantities as needed.

Thank you,
SAS Pulse Automated Replenishment System
            """.strip()

            for manager in store_managers:
                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would email {manager.username}: {subject}")
                else:
                    try:
                        send_mail(
                            subject=subject,
                            message=message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[manager.email],
                            fail_silently=False,
                        )

                        # Log notification
                        ReplenishmentNotification.objects.create(
                            notification_type='store_new_request',
                            recipient=manager,
                            subject=subject,
                            body=message,
                            is_sent=True,
                            sent_at=datetime.now()
                        )

                        sent_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Error sending to {manager.email}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"  ✓ Sent {sent_count} emails to store managers"))

    def send_store_reminders(self, dry_run=False):
        """
        Send reminder emails for pending requests older than 3 days
        """
        self.stdout.write('\n2. Sending REMINDER emails for pending requests...')

        cutoff_date = datetime.now() - timedelta(days=3)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    b.company as branch_name,
                    COUNT(*) as pending_count,
                    SUM(CASE WHEN urgency = 'critical' THEN 1 ELSE 0 END) as critical_count
                FROM dashboard_replenishmentrequest rr
                JOIN cin7_sync_branch b ON b.id = rr.branch_id
                WHERE rr.status = 'pending'
                  AND rr.created_at < %s
                GROUP BY b.company
            """, [cutoff_date])

            branches = cursor.fetchall()

        if not branches:
            self.stdout.write('  No overdue requests found')
            return

        store_managers = CustomUser.objects.filter(is_staff=True, is_active=True)
        sent_count = 0

        for branch_name, pending, critical in branches:
            subject = f"🔔 Reminder: {pending} Pending Replenishment Requests - {branch_name}"

            message = f"""
Hello,

This is a friendly reminder that you have {pending} pending replenishment requests for {branch_name} that need your review.

Summary:
- Pending Requests: {pending}
- Critical Items: {critical}
- Days Pending: 3+ days

Please review these requests as soon as possible:
{settings.SITE_URL}/dashboard/replenishment/store/?status=pending

Thank you,
SAS Pulse Automated Replenishment System
            """.strip()

            for manager in store_managers:
                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would email {manager.username}: {subject}")
                else:
                    try:
                        send_mail(
                            subject=subject,
                            message=message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[manager.email],
                            fail_silently=False,
                        )
                        sent_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"  ✓ Sent {sent_count} reminder emails"))

    def send_dp_batch_notification(self, dry_run=False):
        """
        Send notification to DP team about batch of approved requests ready for review
        """
        self.stdout.write('\n3. Sending batch notification to DP team...')

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN urgency = 'critical' THEN 1 ELSE 0 END) as critical_count,
                    SUM(COALESCE(store_approved_quantity, suggested_quantity)) as total_units,
                    COUNT(DISTINCT product_id) as unique_products,
                    COUNT(DISTINCT branch_id) as unique_branches
                FROM dashboard_replenishmentrequest
                WHERE status IN ('approved', 'modified')
            """)

            row = cursor.fetchone()

            if not row or row[0] == 0:
                self.stdout.write('  No approved requests pending DP review')
                return

            total, critical, units, products, branches = row

        subject = f"📊 {total} Replenishment Requests Ready for DP Review"

        message = f"""
Hello Demand Planning Team,

{total} replenishment requests have been approved by store managers and are ready for your review.

Summary:
- Total Requests: {total}
- Critical Items: {critical}
- Total Units: {int(units)}
- Unique Products: {products}
- Branches Involved: {branches}

Please review and provide final approval:
{settings.SITE_URL}/dashboard/replenishment/dp/

These requests have been reviewed and approved by store managers based on their local knowledge and AI forecasting recommendations.

Action Required:
- Review requests for budget compliance
- Check for supplier consolidation opportunities
- Provide final approval or override quantities as needed

Thank you,
SAS Pulse Automated Replenishment System
        """.strip()

        # Get DP team members (users with 'dp_team' in groups - for now, superusers)
        dp_team = CustomUser.objects.filter(is_superuser=True, is_active=True)

        sent_count = 0

        for member in dp_team:
            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would email {member.username}: {subject}")
            else:
                try:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[member.email],
                        fail_silently=False,
                    )
                    sent_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"  ✓ Sent {sent_count} emails to DP team"))

    def send_dp_urgent_alerts(self, dry_run=False):
        """
        Send urgent alerts to DP team for critical stock situations
        """
        self.stdout.write('\n4. Sending URGENT alerts for critical stock...')

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.name as product_name,
                    b.company as branch_name,
                    rr.current_stock,
                    rr.forecasted_demand_30d,
                    rr.stock_gap,
                    rr.status
                FROM dashboard_replenishmentrequest rr
                JOIN cin7_sync_product p ON p.id = rr.product_id
                JOIN cin7_sync_branch b ON b.id = rr.branch_id
                WHERE rr.urgency = 'critical'
                  AND rr.current_stock = 0
                  AND rr.status IN ('pending', 'approved', 'modified')
                LIMIT 20
            """)

            critical_items = cursor.fetchall()

        if not critical_items:
            self.stdout.write('  No urgent critical items found')
            return

        subject = f"🚨 URGENT: {len(critical_items)} Products with ZERO Stock"

        items_list = "\n".join([
            f"- {item[0][:40]} @ {item[1][:30]}: Stock=0, Forecast={int(item[3])} units"
            for item in critical_items[:10]
        ])

        message = f"""
URGENT ALERT - Demand Planning Team,

{len(critical_items)} products have ZERO stock but forecasted demand for the next 30 days.

Top Critical Items:
{items_list}

{'... and more' if len(critical_items) > 10 else ''}

Immediate Action Required:
Review these critical items urgently and expedite approvals:
{settings.SITE_URL}/dashboard/replenishment/dp/?urgency=critical

SAS Pulse Automated Replenishment System
        """.strip()

        dp_team = CustomUser.objects.filter(is_superuser=True, is_active=True)

        sent_count = 0

        for member in dp_team:
            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would email {member.username}: {subject}")
            else:
                try:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[member.email],
                        fail_silently=False,
                    )
                    sent_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"  ✓ Sent {sent_count} urgent alerts"))
