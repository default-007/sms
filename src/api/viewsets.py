# src/api/viewsets.py
"""Base viewsets and mixins"""

import logging

from django.core.cache import cache
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import BaseFilter
from .paginations import StandardPagination
from .permissions import RoleBasedPermission

logger = logging.getLogger(__name__)


class BaseViewSetMixin:
    """Base mixin for common viewset functionality"""

    permission_classes = [RoleBasedPermission]
    pagination_class = StandardPagination
    filterset_class = BaseFilter

    def get_queryset(self):
        """Override to add common queryset optimizations"""
        queryset = super().get_queryset()

        # Add select_related and prefetch_related if defined
        if hasattr(self, "select_related_fields"):
            queryset = queryset.select_related(*self.select_related_fields)

        if hasattr(self, "prefetch_related_fields"):
            queryset = queryset.prefetch_related(*self.prefetch_related_fields)

        return queryset

    def perform_create(self, serializer):
        """Enhanced create with user tracking"""
        with transaction.atomic():
            instance = serializer.save()

            # Log creation
            logger.info(
                f"Created {instance.__class__.__name__} {instance.id} by {self.request.user}"
            )

            # Clear related cache
            self._clear_related_cache(instance)

    def perform_update(self, serializer):
        """Enhanced update with user tracking"""
        with transaction.atomic():
            instance = serializer.save()

            # Log update
            logger.info(
                f"Updated {instance.__class__.__name__} {instance.id} by {self.request.user}"
            )

            # Clear related cache
            self._clear_related_cache(instance)

    def perform_destroy(self, instance):
        """Enhanced destroy with logging"""
        model_name = instance.__class__.__name__
        instance_id = instance.id

        with transaction.atomic():
            instance.delete()

            # Log deletion
            logger.info(f"Deleted {model_name} {instance_id} by {self.request.user}")

            # Clear related cache
            self._clear_related_cache(instance)

    def _clear_related_cache(self, instance):
        """Clear cache related to the instance"""
        cache_keys = getattr(self, "related_cache_keys", [])
        for key_pattern in cache_keys:
            try:
                cache_key = key_pattern.format(instance=instance)
                cache.delete(cache_key)
            except Exception as e:
                logger.warning(f"Failed to clear cache key {key_pattern}: {e}")

    @action(detail=False, methods=["get"])
    def export(self, request):
        """Export data action"""
        # Implementation depends on export requirements
        return Response({"message": "Export functionality to be implemented"})

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Duplicate instance action"""
        instance = self.get_object()

        # Create copy without unique fields
        duplicated_instance = self._duplicate_instance(instance)

        serializer = self.get_serializer(duplicated_instance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _duplicate_instance(self, instance):
        """Override in subclasses to implement duplication logic"""
        raise NotImplementedError("Duplication not implemented for this model")


class ReadOnlyViewSetMixin(BaseViewSetMixin):
    """Mixin for read-only viewsets"""

    http_method_names = ["get", "head", "options"]


class CachedViewSetMixin:
    """Mixin for cached viewsets"""

    cache_timeout = 300  # 5 minutes default

    def list(self, request, *args, **kwargs):
        """Cached list view"""
        cache_key = self._get_list_cache_key(request)
        cached_response = cache.get(cache_key)

        if cached_response:
            return Response(cached_response)

        response = super().list(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(cache_key, response.data, self.cache_timeout)

        return response

    def retrieve(self, request, *args, **kwargs):
        """Cached retrieve view"""
        cache_key = self._get_detail_cache_key(kwargs.get("pk"))
        cached_response = cache.get(cache_key)

        if cached_response:
            return Response(cached_response)

        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(cache_key, response.data, self.cache_timeout)

        return response

    def _get_list_cache_key(self, request):
        """Generate cache key for list view"""
        params = request.query_params.urlencode()
        return f"{self.__class__.__name__}_list_{hash(params)}"

    def _get_detail_cache_key(self, pk):
        """Generate cache key for detail view"""
        return f"{self.__class__.__name__}_detail_{pk}"
