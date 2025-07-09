from rest_framework import viewsets, permissions
from .models import CustomUser
from .serializers import UserSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer

    # Example of role-based permissions (can be more granular)
    def get_permissions(self):
        # Allow unauthenticated user creation for registration purposes
        if self.action == 'create':
             return [permissions.AllowAny()] # Or a custom permission for registration logic

        # Admins can do anything
        if self.request.user and self.request.user.is_staff: # is_staff is often used for admin-like privileges
            return [permissions.IsAdminUser()]

        # Authenticated users can view/update their own profile
        if self.action in ['retrieve', 'update', 'partial_update']:
            # This check ensures that a user can only access their own details unless they are an admin
            # It's a common pattern, but for strictness, IsOwnerOrAdmin custom permission is better.
            return [permissions.IsAuthenticated()]

        # Default to deny for other actions for non-admins
        return [permissions.IsAdminUser()]


    def get_queryset(self):
        user = self.request.user
        if user.is_staff: # Admin user can see all users
            return CustomUser.objects.all().order_by('-date_joined')
        elif user.is_authenticated: # Non-admin user can only see their own profile
            return CustomUser.objects.filter(pk=user.pk)
        return CustomUser.objects.none() # No queryset for unauthenticated users not creating an account

    # To ensure users can only update their own profile (unless admin)
    # This is implicitly handled by get_queryset for list/retrieve.
    # For update/destroy, ModelViewSet's default behavior relies on the queryset lookup.
    # If a non-admin tries to access /users/{other_user_id}/, get_queryset will return empty, leading to 404.
    # This is generally sufficient for ModelViewSet.
    # For more explicit control, override perform_update, perform_destroy, or use a custom permission class.

    # Note: For user registration, it's often better to have a separate, more tailored endpoint
    # than using the standard UserViewSet create action, especially if you need email verification, etc.
    # The AllowAny on create here is a simplification.
