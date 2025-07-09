from rest_framework import permissions
from users.models import CustomUser # Assuming CustomUser.Role is defined here

class CanChangeRoomStatus(permissions.BasePermission):
    """
    Custom permission to only allow users with specific roles
    (Admin, Front Desk, Housekeeping) to change room status.
    Other actions (like viewing) might be governed by IsAdminOrReadOnly or similar.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Allow read methods for anyone authenticated (or define more granular read permissions elsewhere)
        if request.method in permissions.SAFE_METHODS:
            return True # Or specific logic for who can view rooms

        # For write methods (POST, PUT, PATCH, DELETE), check roles
        # POST (create room) should likely be Admin only.
        # PUT/PATCH (update room, including status) needs role check.
        # DELETE (delete room) should likely be Admin only.

        if view.action in ['update', 'partial_update']:
            # For changing status specifically, these roles are allowed.
            # Other fields in the room might have stricter permissions handled elsewhere if needed.
            return request.user.role in [CustomUser.Role.ADMIN, CustomUser.Role.FRONT_DESK, CustomUser.Role.HOUSEKEEPING]

        # For create and destroy, let's restrict to Admin for now.
        if view.action in ['create', 'destroy']:
            return request.user.role == CustomUser.Role.ADMIN

        return False # Default deny for other actions not explicitly handled

class IsAdminOrReadOnlyForRoomManagement(permissions.BasePermission):
    """
    Allows read access to any authenticated user.
    Allows write access (create, update, delete rooms, roomtypes, amenities) only to Admin users.
    This can be the default permission for RoomTypeViewSet and AmenityViewSet.
    For RoomViewSet, it can be combined with CanChangeRoomStatus for status field.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated # Or just True if anonymous read is desired

        # Write permissions are only allowed to the admin users.
        return request.user and request.user.is_staff and request.user.role == CustomUser.Role.ADMIN

# Note: The IsAdminOrReadOnly permission class in hotel_core/views.py
# was simpler:
# class IsAdminOrReadOnly(permissions.BasePermission):
#     def has_permission(self, request, view):
#         if request.method in permissions.SAFE_METHODS: # GET, HEAD, OPTIONS
#             return True
#         return request.user and request.user.is_staff
# This new IsAdminOrReadOnlyForRoomManagement is more specific about ADMIN role.
# We might want to replace the old one or use this new one specifically.
# The CanChangeRoomStatus is more granular for the status field itself.
# A common pattern is to have a base permission for the ViewSet, and then override
# get_permissions for specific actions or use different serializers for read vs write
# to control which fields are writable by whom.

# For RoomViewSet, if we want general room details editable only by Admin,
# but status editable by Admin, FrontDesk, Housekeeping:
# - Default permission: IsAdminOrReadOnlyForRoomManagement
# - For PATCH to status: Need to ensure only status field is changed by non-Admins
#   or use a separate action.

# Simpler approach for now:
# RoomTypeViewSet, AmenityViewSet: use IsAdminOrReadOnlyForRoomManagement
# RoomViewSet:
#   - Default: IsAdminOrReadOnly (the existing one, allowing staff to edit non-status fields)
#   - For status field updates (PATCH): Check CanChangeRoomStatus logic within the view's partial_update
#     or use a dedicated action for changing status.

# Let's make CanChangeRoomStatus a bit more focused on the *object* permission
# for updating the status field, assuming the viewset itself handles overall create/delete.

class CanUpdateRoomStatusOnly(permissions.BasePermission):
    """
    Allows users with Admin, Front Desk, or Housekeeping roles to update (PATCH)
    a room, but primarily intended to gate the 'status' field.
    Other fields should be handled by serializer validation or another permission layer
    if these roles should not edit them.
    """
    def has_object_permission(self, request, view, obj): # obj is the Room instance
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method == 'PATCH': # Only applies to partial updates
            # Check if 'status' is the only field being updated by non-admins or if it's one of them
            if request.user.role in [CustomUser.Role.ADMIN, CustomUser.Role.FRONT_DESK, CustomUser.Role.HOUSEKEEPING]:
                # If they are these roles, they can PATCH.
                # The serializer should then control if they can *only* patch status vs other fields.
                return True

        # Admin can do full updates (PUT) or other PATCH ops
        if request.user.role == CustomUser.Role.ADMIN:
            return True

        return False # Deny other methods or roles for object-level update

class IsAdminForCreateDestroy(permissions.BasePermission):
    def has_permission(self, request, view):
        if view.action in ['create', 'destroy']:
            return request.user and request.user.is_authenticated and request.user.role == CustomUser.Role.ADMIN
        return True # Allow other actions to be governed by other permissions

# We will use a combination:
# - IsAuthenticated for general authenticated access (reads)
# - IsAdminForCreateDestroy for create/delete on RoomViewSet
# - CanUpdateRoomStatusOnly for PATCH on RoomViewSet (will need to check in view if only status is changed by non-admins)
# - Or, more simply, just a permission that allows PATCH for these roles.
# Let's refine CanChangeRoomStatus to be more direct for the viewset action.

class CanManageSpecificRoomFields(permissions.BasePermission):
    """
    Admin: Can do anything.
    FrontDesk, Housekeeping: Can list, retrieve, and partial_update (primarily for status).
    Other authenticated users: Can only list and retrieve (read-only).
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == CustomUser.Role.ADMIN:
            return True # Admin can do all actions

        if view.action in ['list', 'retrieve']:
            return True # All authenticated users can read

        if view.action in ['partial_update', 'update']: # For PATCH and PUT
            return request.user.role in [CustomUser.Role.FRONT_DESK, CustomUser.Role.HOUSEKEEPING]

        # Create and Destroy are implicitly denied for non-admins by falling through
        return False
