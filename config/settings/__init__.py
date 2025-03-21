# Import appropriate settings based on environment
import os
from .base import *

# Set environment based on DJANGO_SETTINGS_MODULE or default to development
environment = os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.development")

if environment == "config.settings.production":
    from .production import *
elif environment == "config.settings.testing":
    from .testing import *
else:
    from .development import *
