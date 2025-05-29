# src/api/serializers.py
"""Base serializers and mixins"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

User = get_user_model()


class TimestampMixin(serializers.ModelSerializer):
    """Mixin for models with timestamp fields"""

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class UserInfoMixin(serializers.ModelSerializer):
    """Mixin for models with user information"""

    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )
    updated_by_name = serializers.CharField(
        source="updated_by.get_full_name", read_only=True
    )


class BaseModelSerializer(TimestampMixin, UserInfoMixin):
    """Base serializer for most models"""

    class Meta:
        abstract = True

    def create(self, validated_data):
        """Set created_by field on creation"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Set updated_by field on update"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
            validated_data["updated_at"] = timezone.now()
        return super().update(instance, validated_data)


class DynamicFieldsMixin:
    """Mixin to dynamically include/exclude fields"""

    def __init__(self, *args, **kwargs):
        # Extract fields parameter
        fields = kwargs.pop("fields", None)
        exclude = kwargs.pop("exclude", None)

        super().__init__(*args, **kwargs)

        if fields:
            # Include only specified fields
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        elif exclude:
            # Exclude specified fields
            for field_name in exclude:
                self.fields.pop(field_name, None)
