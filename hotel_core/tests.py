from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
import datetime

from .models import Room, RoomType, Amenity, SeasonalPricing, RoomServiceRequest
from users.models import CustomUser
from reservations.models import Reservation, Guest # Needed for testing reservation price calculation

class HotelCoreAPITests(APITestCase):
    def setUp(self):
        # Users
        self.admin_user = CustomUser.objects.create_superuser('admin_hc', 'admin_hc@example.com', 'password123', role=CustomUser.Role.ADMIN)
        self.staff_user = CustomUser.objects.create_user('staff_hc', 'staff_hc@example.com', 'password123', role=CustomUser.Role.FRONT_DESK)
        self.housekeeping_user = CustomUser.objects.create_user('hk_hc', 'hk_hc@example.com', 'password123', role=CustomUser.Role.HOUSEKEEPING)
        self.guest_user_custom = CustomUser.objects.create_user('guest_hc_user', 'guest_hc@example.com', 'password123', role=CustomUser.Role.GUEST)

        # Room Types
        self.double_room_type = RoomType.objects.create(name="Double HC", capacity=2)
        self.suite_room_type = RoomType.objects.create(name="Suite HC", capacity=4)

        # Rooms
        self.room_avail = Room.objects.create(room_number="T101", room_type=self.double_room_type, price_per_night=Decimal("100.00"), status=Room.RoomStatus.AVAILABLE)
        self.room_booked = Room.objects.create(room_number="T102", room_type=self.double_room_type, price_per_night=Decimal("120.00"), status=Room.RoomStatus.BOOKED)
        self.room_maint = Room.objects.create(room_number="T103", room_type=self.suite_room_type, price_per_night=Decimal("250.00"), status=Room.RoomStatus.UNDER_MAINTENANCE)

        # Guest (for reservation testing)
        self.guest_for_res = Guest.objects.create(first_name="Test", last_name="Guest HC", email="testguest.hc@example.com", user_account=self.guest_user_custom)

        self.today = timezone.now().date()


    # --- Seasonal Pricing Tests ---
    def test_room_get_price_for_date_no_rules(self):
        price = self.room_avail.get_price_for_date(self.today)
        self.assertEqual(price, self.room_avail.price_per_night)

    def test_room_get_price_for_date_with_fixed_override(self):
        SeasonalPricing.objects.create(
            room_type=self.double_room_type, name="Summer Special",
            start_date=self.today, end_date=self.today + datetime.timedelta(days=7),
            price_modifier_type=SeasonalPricing.ModifierType.FIXED_OVERRIDE,
            price_modifier_value=Decimal("150.00"), priority=1
        )
        price = self.room_avail.get_price_for_date(self.today)
        self.assertEqual(price, Decimal("150.00"))

    def test_room_get_price_for_date_with_percentage_adjustment(self):
        SeasonalPricing.objects.create(
            room_type=self.double_room_type, name="Weekend Surge",
            start_date=self.today, end_date=self.today + datetime.timedelta(days=2),
            price_modifier_type=SeasonalPricing.ModifierType.PERCENTAGE,
            price_modifier_value=Decimal("20.00"), # +20%
            priority=1
        )
        # Base price is 100.00, +20% = 120.00
        expected_price = self.room_avail.price_per_night * (Decimal('1') + Decimal('0.20'))
        price = self.room_avail.get_price_for_date(self.today)
        self.assertEqual(price, expected_price)

    def test_seasonal_pricing_priority(self):
        # Rule 1: Lower priority, wider range, percentage
        SeasonalPricing.objects.create(
            room_type=self.double_room_type, name="General Discount",
            start_date=self.today - datetime.timedelta(days=5), end_date=self.today + datetime.timedelta(days=5),
            price_modifier_type=SeasonalPricing.ModifierType.PERCENTAGE,
            price_modifier_value=Decimal("-10.00"), # -10% -> 90.00
            priority=0
        )
        # Rule 2: Higher priority, specific date, fixed override
        SeasonalPricing.objects.create(
            room_type=self.double_room_type, name="Today Only Special",
            start_date=self.today, end_date=self.today,
            price_modifier_type=SeasonalPricing.ModifierType.FIXED_OVERRIDE,
            price_modifier_value=Decimal("130.00"), # Override to 130.00
            priority=10
        )
        price = self.room_avail.get_price_for_date(self.today)
        self.assertEqual(price, Decimal("130.00")) # Higher priority rule should apply

    def test_reservation_price_calculation_with_seasonal_pricing(self):
        # Room T101, base price 100
        # Day 1 (today): Special price 130 (from test_seasonal_pricing_priority setup)
        # Day 2 (tomorrow): General discount -10% -> 90
        SeasonalPricing.objects.create(
            room_type=self.double_room_type, name="General Discount",
            start_date=self.today - datetime.timedelta(days=5), end_date=self.today + datetime.timedelta(days=5),
            price_modifier_type=SeasonalPricing.ModifierType.PERCENTAGE,
            price_modifier_value=Decimal("-10.00"), priority=0
        )
        SeasonalPricing.objects.create(
            room_type=self.double_room_type, name="Today Only Special",
            start_date=self.today, end_date=self.today,
            price_modifier_type=SeasonalPricing.ModifierType.FIXED_OVERRIDE,
            price_modifier_value=Decimal("130.00"), priority=10
        )

        reservation = Reservation(
            guest=self.guest_for_res, room=self.room_avail,
            check_in_date=self.today,
            check_out_date=self.today + datetime.timedelta(days=2) # 2 nights
        )
        # Price for today = 130
        # Price for tomorrow = 100 * 0.90 = 90
        # Total base = 130 + 90 = 220
        expected_base_price = Decimal("130.00") + Decimal("90.00")
        self.assertEqual(reservation.calculate_total_price(), expected_base_price)

        # Test save also considers this (without extra fees for now)
        reservation.save() # This calls calculate_total_price and then adds fees (0 here)
        self.assertEqual(reservation.total_price, expected_base_price)


    def test_admin_crud_seasonal_pricing(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('seasonalpricing-list')
        data = {
            "room_type": self.suite_room_type.pk, # This should be the ID
            "name": "Suite Christmas Peak",
            "start_date": (self.today + datetime.timedelta(days=30)).isoformat(),
            "end_date": (self.today + datetime.timedelta(days=40)).isoformat(),
            "price_modifier_type": SeasonalPricing.ModifierType.FIXED_OVERRIDE,
            "price_modifier_value": "350.00",
            "priority": 5
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(SeasonalPricing.objects.count(), 1)
        rule_id = response.data['id']

        # Update
        patch_data = {"price_modifier_value": "375.00"}
        patch_url = reverse('seasonalpricing-detail', kwargs={'pk': rule_id})
        response_patch = self.client.patch(patch_url, patch_data, format='json')
        self.assertEqual(response_patch.status_code, status.HTTP_200_OK, response_patch.data)
        self.assertEqual(Decimal(response_patch.data['price_modifier_value']), Decimal("375.00")) # Compare Decimals

        # Delete
        response_delete = self.client.delete(patch_url)
        self.assertEqual(response_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(SeasonalPricing.objects.count(), 0)


    # --- Manual Room Status Override Tests ---
    def test_staff_can_change_room_status(self):
        self.client.force_authenticate(user=self.housekeeping_user)
        url = reverse('room-detail', kwargs={'pk': self.room_avail.pk})
        # room_avail is currently AVAILABLE

        # HK changes to NEEDS_CLEANING
        response = self.client.patch(url, {"status": Room.RoomStatus.NEEDS_CLEANING}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.room_avail.refresh_from_db()
        self.assertEqual(self.room_avail.status, Room.RoomStatus.NEEDS_CLEANING)

        # Front Desk changes to AVAILABLE
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.patch(url, {"status": Room.RoomStatus.AVAILABLE}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.room_avail.refresh_from_db()
        self.assertEqual(self.room_avail.status, Room.RoomStatus.AVAILABLE)

    def test_unauthorized_user_cannot_change_room_status(self):
        # A guest user should not be able to change room status
        self.client.force_authenticate(user=self.guest_user_custom)
        url = reverse('room-detail', kwargs={'pk': self.room_avail.pk})
        response = self.client.patch(url, {"status": Room.RoomStatus.UNDER_MAINTENANCE}, format='json')
        # Based on CanManageSpecificRoomFields, GUEST role does not have update/partial_update
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    # --- Room Service Request Tests ---
    def test_staff_create_room_service_request(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('roomservicerequest-list')
        reservation = Reservation.objects.create(
            guest=self.guest_for_res, room=self.room_avail,
            check_in_date=self.today, check_out_date=self.tomorrow,
            status=Reservation.ReservationStatus.CHECKED_IN
        )
        data = {
            "room_id": self.room_avail.pk,
            "reservation_id": reservation.pk,
            "request_type": RoomServiceRequest.RequestType.FOOD_BEVERAGE,
            "description": "Order 2 Cokes",
            "price": "5.00" # Staff can set price
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(RoomServiceRequest.objects.count(), 1)
        rsr = RoomServiceRequest.objects.first()
        self.assertEqual(rsr.requested_by, self.staff_user)
        self.assertEqual(rsr.room, self.room_avail)
        self.assertEqual(rsr.price, Decimal("5.00"))

    def test_staff_update_room_service_request_status(self):
        self.client.force_authenticate(user=self.staff_user)
        rsr = RoomServiceRequest.objects.create(
            room=self.room_avail, requested_by=self.staff_user,
            description="Initial request", request_type=RoomServiceRequest.RequestType.OTHER
        )
        url = reverse('roomservicerequest-detail', kwargs={'pk': rsr.pk})

        # Staff updates status to COMPLETED and assigns self
        update_data = {
            "status": RoomServiceRequest.RequestStatus.COMPLETED,
            "assigned_to": self.staff_user.pk, # Assign to self
            "notes": "Delivered by front desk."
        }
        response = self.client.patch(url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        rsr.refresh_from_db()
        self.assertEqual(rsr.status, RoomServiceRequest.RequestStatus.COMPLETED)
        self.assertEqual(rsr.assigned_to, self.staff_user)
        self.assertIsNotNone(rsr.completed_at)
        self.assertEqual(rsr.notes, "Delivered by front desk.")

    # Add tests for guest creating service request (needs guest authentication and viewset permission adjustment)
    # Add tests for other staff roles (Housekeeping) managing specific request types or statuses.
    # Add tests for filtering room service requests.
    # Add tests for price calculation being added to a folio/bill (future phase).

# Remember to create the actual URL patterns for these views in hotel_core/urls.py
# (e.g., router.register(r'seasonal-pricing', SeasonalPricingViewSet, basename='seasonalpricing'))
# and ensure CustomUser and Reservation models are correctly imported and set up.
# For room-detail, if RoomViewSet basename is 'room', then reverse('room-detail', ...) is correct.
# For roomservicerequest-list and -detail, if basename is 'roomservicerequest', it's correct.

    # --- Phase 5: Housekeeping Management Tests ---

    # 1. Room Cleaning Schedule (API Access)
    def test_list_rooms_needing_cleaning(self):
        self.client.force_authenticate(user=self.housekeeping_user)
        # Ensure one room is NEEDS_CLEANING
        self.room_avail.status = Room.RoomStatus.NEEDS_CLEANING
        self.room_avail.save()
        # self.room_booked is BOOKED
        # self.room_maint is UNDER_MAINTENANCE

        url = reverse('room-list') # Assuming RoomViewSet is registered with basename 'room'
        response = self.client.get(f"{url}?status={Room.RoomStatus.NEEDS_CLEANING}")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.room_avail.id)
        self.assertEqual(response.data['results'][0]['status'], Room.RoomStatus.NEEDS_CLEANING)

    # 2. Cleaning Assignments
    def test_create_cleaning_assignment_by_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        self.room_avail.status = Room.RoomStatus.NEEDS_CLEANING # Room must need cleaning for assignment
        self.room_avail.save()

        url = reverse('cleaningassignment-list') # Basename 'cleaningassignment'
        data = {
            "room_id": self.room_avail.pk,
            "assigned_to_id": self.housekeeping_user.pk,
            "notes": "Guest requested quick turnaround."
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(CleaningAssignment.objects.count(), 1)
        assignment = CleaningAssignment.objects.first()
        self.assertEqual(assignment.room, self.room_avail)
        self.assertEqual(assignment.assigned_to, self.housekeeping_user)
        self.assertEqual(assignment.status, CleaningAssignment.AssignmentStatus.PENDING)

    def test_housekeeping_staff_update_own_assignment_status(self):
        self.client.force_authenticate(user=self.housekeeping_user)
        assignment = CleaningAssignment.objects.create(
            room=self.room_avail,
            assigned_to=self.housekeeping_user,
            status=CleaningAssignment.AssignmentStatus.PENDING
        )
        self.room_avail.status = Room.RoomStatus.NEEDS_CLEANING # Prerequisite for the signal later
        self.room_avail.save()

        url = reverse('cleaningassignment-detail', kwargs={'pk': assignment.pk})

        # HK staff updates to IN_PROGRESS
        response_inprogress = self.client.patch(url, {"status": CleaningAssignment.AssignmentStatus.IN_PROGRESS}, format='json')
        self.assertEqual(response_inprogress.status_code, status.HTTP_200_OK, response_inprogress.data)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, CleaningAssignment.AssignmentStatus.IN_PROGRESS)

        # HK staff updates to COMPLETED
        response_completed = self.client.patch(url, {"status": CleaningAssignment.AssignmentStatus.COMPLETED}, format='json')
        self.assertEqual(response_completed.status_code, status.HTTP_200_OK, response_completed.data)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, CleaningAssignment.AssignmentStatus.COMPLETED)
        self.assertIsNotNone(assignment.cleaned_at)

        # Check if room status was updated to AVAILABLE by the signal
        self.room_avail.refresh_from_db()
        self.assertEqual(self.room_avail.status, Room.RoomStatus.AVAILABLE)

    def test_signal_auto_creates_cleaning_assignment(self):
        # Initial state: room is AVAILABLE, no cleaning assignments
        self.room_booked.status = Room.RoomStatus.AVAILABLE
        self.room_booked.save()
        self.assertEqual(CleaningAssignment.objects.filter(room=self.room_booked).count(), 0)

        # Change room status to NEEDS_CLEANING - signal should fire
        self.room_booked.status = Room.RoomStatus.NEEDS_CLEANING
        self.room_booked.save()

        self.assertEqual(CleaningAssignment.objects.filter(room=self.room_booked).count(), 1)
        assignment = CleaningAssignment.objects.get(room=self.room_booked)
        self.assertEqual(assignment.status, CleaningAssignment.AssignmentStatus.PENDING)
        self.assertIsNone(assignment.assigned_to) # Initially unassigned

    # 3. Maintenance Ticketing System (Leveraging RoomServiceRequest)
    def test_create_maintenance_request_and_assign_to_maintenance_staff(self):
        self.client.force_authenticate(user=self.admin_user) # Admin creates and assigns
        maintenance_staff = CustomUser.objects.create_user(
            username='maint_staff', email='maint@example.com', password='password123',
            role=CustomUser.Role.MAINTENANCE
        )
        url = reverse('roomservicerequest-list')
        data = {
            "room_id": self.room_avail.pk,
            "request_type": RoomServiceRequest.RequestType.MAINTENANCE_ISSUE,
            "description": "Shower head broken.",
            "assigned_to_id": maintenance_staff.pk # Assign directly
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        rsr = RoomServiceRequest.objects.get(pk=response.data['id'])
        self.assertEqual(rsr.request_type, RoomServiceRequest.RequestType.MAINTENANCE_ISSUE)
        self.assertEqual(rsr.assigned_to, maintenance_staff)

    def test_maintenance_staff_updates_own_ticket_and_room_status_changes(self):
        maintenance_staff = CustomUser.objects.create_user(
            username='maint_staff2', email='maint2@example.com', password='password123',
            role=CustomUser.Role.MAINTENANCE
        )
        self.client.force_authenticate(user=maintenance_staff)

        # Admin creates the ticket first
        admin_client = APITestCase() # New client for admin actions
        admin_client.force_authenticate(user=self.admin_user)
        rsr_data = {
            "room_id": self.room_avail.pk,
            "request_type": RoomServiceRequest.RequestType.MAINTENANCE_ISSUE,
            "description": "AC not cooling",
            "assigned_to_id": maintenance_staff.pk
        }
        rsr_create_url = reverse('roomservicerequest-list')
        admin_client.post(rsr_create_url, rsr_data, format='json')
        rsr = RoomServiceRequest.objects.get(description="AC not cooling")

        self.room_avail.status = Room.RoomStatus.AVAILABLE # Ensure room is available initially
        self.room_avail.save()

        url = reverse('roomservicerequest-detail', kwargs={'pk': rsr.pk})

        # Maintenance staff sets to IN_PROGRESS
        response_inprogress = self.client.patch(url, {"status": RoomServiceRequest.RequestStatus.IN_PROGRESS}, format='json')
        self.assertEqual(response_inprogress.status_code, status.HTTP_200_OK, response_inprogress.data)
        rsr.refresh_from_db()
        self.assertEqual(rsr.status, RoomServiceRequest.RequestStatus.IN_PROGRESS)
        # Check room status changed to UNDER_MAINTENANCE
        self.room_avail.refresh_from_db()
        self.assertEqual(self.room_avail.status, Room.RoomStatus.UNDER_MAINTENANCE)

        # Maintenance staff sets to COMPLETED
        response_completed = self.client.patch(url, {"status": RoomServiceRequest.RequestStatus.COMPLETED}, format='json')
        self.assertEqual(response_completed.status_code, status.HTTP_200_OK, response_completed.data)
        rsr.refresh_from_db()
        self.assertEqual(rsr.status, RoomServiceRequest.RequestStatus.COMPLETED)
        # Check room status changed back to AVAILABLE
        self.room_avail.refresh_from_db()
        self.assertEqual(self.room_avail.status, Room.RoomStatus.AVAILABLE)

    # Linen management models are structure-only for now, no API tests.
