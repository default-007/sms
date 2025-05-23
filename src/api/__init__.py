# src/api/__init__.py
"""
School Management System API Module

This module provides common utilities, authentication, permissions, and routing
for the entire API infrastructure. Individual apps manage their own endpoints.
"""

__version__ = "2.0.0"
__author__ = "School Management System Team"

default_app_config = "src.api.apps.ApiConfig"
