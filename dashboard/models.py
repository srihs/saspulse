"""
Dashboard Models

Additional models for dashboard analytics and caching
"""

from django.db import models
from django.utils import timezone


class DashboardCache(models.Model):
    """
    Cache computed dashboard metrics to improve performance
    """
    cache_key = models.CharField(max_length=255, unique=True, db_index=True)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['cache_key']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.cache_key} (expires: {self.expires_at})"

    @property
    def is_expired(self):
        """Check if cache has expired"""
        return timezone.now() > self.expires_at

    @classmethod
    def get_or_none(cls, cache_key):
        """Get cached data if not expired"""
        try:
            cache = cls.objects.get(cache_key=cache_key)
            if cache.is_expired:
                cache.delete()
                return None
            return cache.data
        except cls.DoesNotExist:
            return None

    @classmethod
    def set_cache(cls, cache_key, data, ttl_minutes=60):
        """Set cache data with TTL"""
        expires_at = timezone.now() + timezone.timedelta(minutes=ttl_minutes)
        cache, created = cls.objects.update_or_create(
            cache_key=cache_key,
            defaults={
                'data': data,
                'expires_at': expires_at
            }
        )
        return cache
