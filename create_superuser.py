#!/usr/bin/env python
"""
Script to create a Django superuser non-interactively.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
os.environ['USE_SQLITE'] = 'True'
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Superuser credentials
username = 'admin'
email = 'admin@schoolsms.com'
password = 'admin123'  # Change this in production!
first_name = 'System'
last_name = 'Administrator'

# Check if superuser already exists
if User.objects.filter(username=username).exists():
    print(f'Superuser "{username}" already exists.')
else:
    # Create superuser
    user = User.objects.create_superuser(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name
    )
    print(f'Superuser "{username}" created successfully!')
    print(f'Username: {username}')
    print(f'Password: {password}')
    print(f'Email: {email}')
    print('\n⚠️  IMPORTANT: Change the password after first login!')
