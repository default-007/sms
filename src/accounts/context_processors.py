def user_roles(request):
    """Add user roles to the template context."""
    context = {"user_roles": []}

    if request.user.is_authenticated:
        # Get assigned roles
        roles = request.user.get_assigned_roles()
        role_names = [role.name for role in roles]

        context["user_roles"] = role_names

        # Add is_admin flag
        context["is_admin"] = request.user.is_superuser or "Admin" in role_names

    return context
