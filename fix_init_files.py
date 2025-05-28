#!/usr/bin/env python3
"""
Comprehensive fix script for Django App Registry issues in School Management System.
Run this from your project root directory.
"""

import os
import shutil
import glob
from datetime import datetime


def create_backup():
    """Create backup of current init files"""
    backup_dir = f"backup_init_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)

    init_files = glob.glob("src/*/__init__.py")
    for init_file in init_files:
        if os.path.exists(init_file):
            backup_path = os.path.join(
                backup_dir, os.path.basename(os.path.dirname(init_file)) + "_init.py"
            )
            shutil.copy2(init_file, backup_path)

    print(f"✅ Created backup in: {backup_dir}")
    return backup_dir


def fix_all_init_files():
    """Fix all __init__.py files in the School Management System"""

    print("🚀 School Management System - Django App Registry Fix")
    print("=" * 60)

    # Create backup first
    backup_dir = create_backup()

    # App configurations based on your system structure
    app_configs = {
        "accounts": {
            "description": "User accounts and authentication",
            "config_class": "AccountsConfig",
        },
        "students": {
            "description": "Student management and profiles",
            "config_class": "StudentsConfig",
        },
        "teachers": {
            "description": "Teacher management and assignments",
            "config_class": "TeachersConfig",
        },
        "academics": {
            "description": "Academic structure (sections, grades, classes)",
            "config_class": "AcademicsConfig",
        },
        "subjects": {
            "description": "Subjects and syllabus management",
            "config_class": "SubjectsConfig",
        },
        "scheduling": {
            "description": "Timetable and scheduling",
            "config_class": "SchedulingConfig",
        },
        "assignments": {
            "description": "Assignment management",
            "config_class": "AssignmentsConfig",
        },
        "exams": {
            "description": "Examinations and assessments",
            "config_class": "ExamsConfig",
        },
        "attendance": {
            "description": "Attendance tracking",
            "config_class": "AttendanceConfig",
        },
        "finance": {
            "description": "Fee management and payments",
            "config_class": "FinanceConfig",
        },
        "library": {
            "description": "Library management",
            "config_class": "LibraryConfig",
        },
        "transport": {
            "description": "Transportation management",
            "config_class": "TransportConfig",
        },
        "communications": {
            "description": "Notifications and messaging",
            "config_class": "CommunicationsConfig",
        },
        "analytics": {
            "description": "Analytics and reporting",
            "config_class": "AnalyticsConfig",
        },
        "reports": {
            "description": "Report generation",
            "config_class": "ReportsConfig",
        },
        "core": {
            "description": "Core utilities and shared functionality",
            "config_class": "CoreConfig",
        },
        "api": {
            "description": "API utilities and common functionality",
            "config_class": "ApiConfig",
        },
    }

    # Find and fix all __init__.py files
    fixed_count = 0

    for app_name, config in app_configs.items():
        init_file = f"src/{app_name}/__init__.py"

        if os.path.exists(init_file):
            # Create clean __init__.py content
            content = f'''"""
{config['description']} for the School Management System.
"""

default_app_config = 'src.{app_name}.apps.{config['config_class']}'
'''

            try:
                with open(init_file, "w") as f:
                    f.write(content)
                print(f"✅ Fixed: {init_file}")
                fixed_count += 1
            except Exception as e:
                print(f"❌ Error fixing {init_file}: {e}")
        else:
            print(f"⚠️  Not found: {init_file}")

    print("=" * 60)
    print(f"🎉 Successfully fixed {fixed_count} __init__.py files!")

    # Check for potential model import issues
    check_model_imports()

    # Provide next steps
    print_next_steps()


def check_model_imports():
    """Check for potential circular import issues in models.py files"""

    print("\n🔍 Checking for potential circular import issues...")
    print("-" * 40)

    model_files = glob.glob("src/*/models.py")
    issues_found = False

    for model_file in model_files:
        app_name = os.path.basename(os.path.dirname(model_file))

        try:
            with open(model_file, "r") as f:
                content = f.read()

            # Check for problematic import patterns
            problematic_patterns = [
                ("from src.", "Direct imports from src package"),
                ("import src.", "Direct imports from src package"),
            ]

            for pattern, description in problematic_patterns:
                if pattern in content:
                    print(f"⚠️  {model_file}: {description}")
                    print(f"   Found: {pattern}")
                    issues_found = True

        except Exception as e:
            print(f"❌ Error checking {model_file}: {e}")

    if not issues_found:
        print("✅ No obvious circular import issues found")
    else:
        print("\n💡 Fix suggestions:")
        print("   • Use string references: 'accounts.User' instead of importing User")
        print("   • Use settings.AUTH_USER_MODEL for user references")
        print("   • Import models locally in functions/methods when needed")


def print_next_steps():
    """Print next steps for the user"""

    print("\n📋 Next Steps:")
    print("-" * 40)
    print("1. 🧪 Test the fix:")
    print("   python manage.py makemigrations")
    print()
    print("2. 🔧 If you still get errors, check for:")
    print("   • Circular imports between models")
    print("   • Direct model imports in other __init__.py files")
    print("   • Missing apps in INSTALLED_APPS")
    print()
    print("3. 🚀 Common fixes for remaining issues:")
    print("   • In models.py, use 'app.Model' instead of importing Model")
    print("   • Use settings.AUTH_USER_MODEL for User references")
    print("   • Import models locally in functions where needed")
    print()
    print("4. 📖 Example fixes:")
    print("   ❌ from src.accounts.models import User")
    print("   ✅ user = models.ForeignKey('accounts.User', ...)")
    print("   ✅ user = models.ForeignKey(settings.AUTH_USER_MODEL, ...)")


def emergency_clean():
    """Emergency clean - make all __init__.py files minimal"""

    print("🚨 Emergency clean mode - making all __init__.py files minimal")

    init_files = glob.glob("src/*/__init__.py")
    for init_file in init_files:
        app_name = os.path.basename(os.path.dirname(init_file))

        minimal_content = f'''"""
{app_name.title()} app for the School Management System.
"""

default_app_config = 'src.{app_name}.apps.{app_name.title()}Config'
'''

        try:
            with open(init_file, "w") as f:
                f.write(minimal_content)
            print(f"✅ Cleaned: {init_file}")
        except Exception as e:
            print(f"❌ Error cleaning {init_file}: {e}")


if __name__ == "__main__":
    import sys

    # Check if we're in the right directory
    if not os.path.exists("src"):
        print("❌ 'src' directory not found!")
        print("Please run this script from your project root directory")
        sys.exit(1)

    if not os.path.exists("manage.py"):
        print("❌ 'manage.py' not found!")
        print("Please run this script from your Django project root directory")
        sys.exit(1)

    # Check for emergency clean mode
    if len(sys.argv) > 1 and sys.argv[1] == "--emergency":
        emergency_clean()
    else:
        fix_all_init_files()

    print("\n🎯 Now try: python manage.py makemigrations")
    print("💡 If problems persist, run with --emergency flag for minimal cleanup")
