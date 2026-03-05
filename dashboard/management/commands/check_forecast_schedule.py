"""
Check Forecast Schedule and Identify Forecasts Due for Regeneration

This management command checks the ForecastSchedule model to identify
forecasts that are due or overdue for regeneration. It can optionally
trigger automatic regeneration and send notifications.

Usage:
    python manage.py check_forecast_schedule                # Check only
    python manage.py check_forecast_schedule --regenerate   # Auto-regenerate
    python manage.py check_forecast_schedule --notify       # Send notifications
    python manage.py check_forecast_schedule --all          # Both regenerate and notify

Typical cron setup (daily at 2 AM):
    0 2 * * * cd /path/to/saspulse && python manage.py check_forecast_schedule --regenerate
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.management import call_command
from dashboard.models import ForecastSchedule, SalesForecastBase
from datetime import timedelta


class Command(BaseCommand):
    help = 'Check forecast schedule and identify forecasts due for regeneration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--regenerate',
            action='store_true',
            help='Automatically regenerate forecasts that are due'
        )
        parser.add_argument(
            '--notify',
            action='store_true',
            help='Send email notifications for overdue forecasts'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Regenerate and notify (shortcut for --regenerate --notify)'
        )
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=7,
            help='Include forecasts due within N days (default: 7)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('FORECAST SCHEDULE HEALTH CHECK'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        regenerate = options['regenerate'] or options['all']
        notify = options['notify'] or options['all']
        days_ahead = options['days_ahead']

        # Update all forecast statuses
        self.stdout.write('\nUpdating forecast statuses...')
        updated_count = 0
        for schedule in ForecastSchedule.objects.all():
            schedule.update_status()
            updated_count += 1

        self.stdout.write(self.style.SUCCESS(f'✓ Updated {updated_count} forecast schedules'))

        # Get current statistics
        now = timezone.now()
        total = ForecastSchedule.objects.count()
        current = ForecastSchedule.objects.filter(status='current').count()
        due = ForecastSchedule.objects.filter(status='due').count()
        overdue = ForecastSchedule.objects.filter(status='overdue').count()

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.WARNING('OVERALL STATISTICS'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total Forecasts:    {total}')
        self.stdout.write(self.style.SUCCESS(f'Current:            {current} ({current/total*100:.1f}%)'))
        self.stdout.write(self.style.WARNING(f'Due:                {due} ({due/total*100:.1f}%)'))
        self.stdout.write(self.style.ERROR(f'Overdue:            {overdue} ({overdue/total*100:.1f}%)'))

        # Breakdown by aggregation level
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.WARNING('BREAKDOWN BY AGGREGATION LEVEL'))
        self.stdout.write('=' * 80)

        from django.db.models import Count, Q

        level_stats = ForecastSchedule.objects.values('aggregation_level').annotate(
            total=Count('id'),
            current_count=Count('id', filter=Q(status='current')),
            due_count=Count('id', filter=Q(status='due')),
            overdue_count=Count('id', filter=Q(status='overdue'))
        ).order_by('aggregation_level')

        for stat in level_stats:
            level = stat['aggregation_level']
            total_level = stat['total']
            current_level = stat['current_count']
            due_level = stat['due_count']
            overdue_level = stat['overdue_count']

            self.stdout.write(
                f"\n{level.upper()}:"
                f"\n  Total: {total_level} | "
                f"Current: {current_level} | "
                f"Due: {due_level} | "
                f"Overdue: {overdue_level}"
            )

        # Get forecasts due for regeneration
        due_threshold = now + timedelta(days=days_ahead)
        forecasts_needing_action = ForecastSchedule.objects.filter(
            next_generation_due__lte=due_threshold
        ).order_by('next_generation_due')

        if forecasts_needing_action.exists():
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.ERROR(f'FORECASTS DUE FOR REGENERATION (Next {days_ahead} days)'))
            self.stdout.write('=' * 80)

            for schedule in forecasts_needing_action[:20]:  # Show first 20
                days_until = (schedule.next_generation_due - now).days
                days_since = schedule.days_since_generated

                status_style = self.style.SUCCESS if schedule.status == 'current' else (
                    self.style.WARNING if schedule.status == 'due' else self.style.ERROR
                )

                self.stdout.write(
                    f"\n{status_style(schedule.status.upper())} | "
                    f"{schedule.entity_name[:40]:40} | "
                    f"{schedule.aggregation_level:10} | "
                    f"Days until due: {days_until:4} | "
                    f"Days since generated: {days_since:4}"
                )

            if forecasts_needing_action.count() > 20:
                self.stdout.write(f"\n... and {forecasts_needing_action.count() - 20} more")

            # Regenerate if requested
            if regenerate:
                self.stdout.write('\n' + '=' * 80)
                self.stdout.write(self.style.WARNING('REGENERATING FORECASTS'))
                self.stdout.write('=' * 80)

                # Group by aggregation level for efficient regeneration
                levels_to_regenerate = forecasts_needing_action.values_list(
                    'aggregation_level', flat=True
                ).distinct()

                for level in levels_to_regenerate:
                    self.stdout.write(f'\nRegenerating {level} forecasts...')
                    try:
                        call_command('generate_365d_forecasts', level=level, force=True)
                        self.stdout.write(self.style.SUCCESS(f'✓ Regenerated {level} forecasts'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'✗ Error regenerating {level}: {e}'))

            # Send notifications if requested
            if notify:
                self.stdout.write('\n' + '=' * 80)
                self.stdout.write(self.style.WARNING('SENDING NOTIFICATIONS'))
                self.stdout.write('=' * 80)

                overdue_forecasts = ForecastSchedule.objects.filter(status='overdue')
                if overdue_forecasts.exists():
                    self.send_notification_email(overdue_forecasts)
                else:
                    self.stdout.write('No overdue forecasts - no notifications needed')

        else:
            self.stdout.write('\n' + self.style.SUCCESS('✓ All forecasts are current - no action needed'))

        # Show oldest forecasts (potential issues)
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.WARNING('OLDEST FORECASTS (potential staleness)'))
        self.stdout.write('=' * 80)

        oldest_forecasts = SalesForecastBase.objects.order_by('forecast_date')[:10]
        for forecast in oldest_forecasts:
            days_old = (now.date() - forecast.forecast_date).days
            self.stdout.write(
                f"{forecast.entity_name[:40]:40} | "
                f"{forecast.aggregation_level:10} | "
                f"Generated: {forecast.forecast_date} ({days_old} days ago)"
            )

        self.stdout.write('\n' + self.style.SUCCESS('✓ Forecast schedule check complete!'))

    def send_notification_email(self, overdue_forecasts):
        """
        Send email notification about overdue forecasts
        Requires email configuration in Django settings
        """
        try:
            from django.core.mail import send_mail
            from django.conf import settings

            subject = f'[SASPulse] {overdue_forecasts.count()} Forecasts Overdue for Regeneration'

            message = f"""
Forecast Schedule Health Alert
================================

There are {overdue_forecasts.count()} forecasts that are OVERDUE for regeneration.

Overdue Forecasts:
"""

            for schedule in overdue_forecasts[:50]:  # Limit to 50 in email
                days_overdue = abs(schedule.days_until_due)
                message += f"\n- {schedule.entity_name} ({schedule.aggregation_level}) - {days_overdue} days overdue"

            message += f"""

Action Required:
----------------
Run the following command to regenerate forecasts:

    python manage.py generate_365d_forecasts --force

Or visit the Forecast Health Dashboard:
    http://your-domain/dashboard/forecasting/health/

Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            # Send to admins (configured in settings.ADMINS)
            recipient_list = [email for name, email in settings.ADMINS] if hasattr(settings, 'ADMINS') else []

            if recipient_list:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    recipient_list,
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Notification sent to {len(recipient_list)} recipients'))
            else:
                self.stdout.write(self.style.WARNING('⚠ No recipients configured (settings.ADMINS is empty)'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error sending notification: {e}'))
