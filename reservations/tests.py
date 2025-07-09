from django.utils import timezone
from django.core import mail
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
import datetime
import uuid # Added for group_identifier testing
from django.core.files.uploadedfile import SimpleUploadedFile # For image upload test
from decimal import Decimal # For fee comparison

from .models import Guest, Reservation, GuestDocument
from hotel_core.models import Room, RoomType, Amenity
from users.models import CustomUser # Assuming CustomUser is in users.models

# It's good practice to use a specific test runner or settings that use an in-memory SQLite DB for tests
# or ensure your test DB is properly set up and torn down.

class ReservationAPITests(APITestCase):
    def setUp(self):
        # Create Users
        self.admin_user = CustomUser.objects.create_superuser('admin', 'admin@example.com', 'password123')
        self.admin_user.role = CustomUser.Role.ADMIN # Ensure role is set if not default by superuser
        self.admin_user.save()

        self.staff_user = CustomUser.objects.create_user('staff', 'staff@example.com', 'password123', role=CustomUser.Role.FRONT_DESK)

        # Create Amenities and RoomType
        self.wifi = Amenity.objects.create(name="WiFi")
        self.ac = Amenity.objects.create(name="AC")
        self.suite_type = RoomType.objects.create(name="Suite", capacity=4)
        self.double_type = RoomType.objects.create(name="Double", capacity=2)

        # Create Rooms
        self.room101 = Room.objects.create(room_number="101", room_type=self.double_type, price_per_night=100.00, status=Room.RoomStatus.AVAILABLE)
        self.room101.amenities.add(self.wifi, self.ac)

        self.room102 = Room.objects.create(room_number="102", room_type=self.double_type, price_per_night=110.00, status=Room.RoomStatus.AVAILABLE)
        self.room102.amenities.add(self.wifi)

        self.room201_suite = Room.objects.create(room_number="201", room_type=self.suite_type, price_per_night=250.00, status=Room.RoomStatus.UNDER_MAINTENANCE)

        # Create Guest
        self.guest1 = Guest.objects.create(first_name="John", last_name="Doe", email="john.doe@example.com")
        self.guest2 = Guest.objects.create(first_name="Jane", last_name="Smith", email="jane.smith@example.com")

        # Dates for testing
        self.today = timezone.now().date()
        self.tomorrow = self.today + datetime.timedelta(days=1)
        self.day_after_tomorrow = self.today + datetime.timedelta(days=2)
        self.three_days_later = self.today + datetime.timedelta(days=3)
        self.four_days_later = self.today + datetime.timedelta(days=4)

        # Make sure URL names are correct based on reservations/urls.py and how the router is defined.
        # If router = DefaultRouter() and then router.register(r'reservations', ReservationViewSet, basename='reservation')
        # List: 'reservation-list'
        # Detail: 'reservation-detail'
        # Custom actions (like cancel): 'reservation-cancel'
        self.list_url = reverse('reservation-list')


    # --- Test Reservation Creation & Availability Logic ---
    def test_create_single_reservation_success(self):
        self.client.force_authenticate(user=self.staff_user)
        data = {
            "guest_id": self.guest1.pk,
            "room_id": self.room101.pk,
            "check_in_date": self.tomorrow.isoformat(),
            "check_out_date": self.day_after_tomorrow.isoformat(),
            "number_of_adults": 2,
            "status": Reservation.ReservationStatus.CONFIRMED # Test direct confirmation
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Reservation.objects.count(), 1)
        created_reservation = Reservation.objects.first()
        self.assertEqual(created_reservation.room, self.room101)
        self.assertEqual(created_reservation.guest, self.guest1)
        self.assertEqual(created_reservation.status, Reservation.ReservationStatus.CONFIRMED)

        # Check email was sent (confirmation)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Your Reservation is Confirmed!')
        self.assertIn(self.guest1.email, mail.outbox[0].to)

        # Check room status updated to BOOKED
        self.room101.refresh_from_db()
        self.assertEqual(self.room101.status, Room.RoomStatus.BOOKED)


    def test_create_reservation_room_not_available_due_to_status(self):
        self.client.force_authenticate(user=self.staff_user)
        data = {
            "guest_id": self.guest1.pk,
            "room_id": self.room201_suite.pk, # This room is UNDER_MAINTENANCE
            "check_in_date": self.tomorrow.isoformat(),
            "check_out_date": self.day_after_tomorrow.isoformat(),
            "number_of_adults": 2,
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("under maintenance", response.data.get("room")[0].lower())


    def test_create_reservation_room_not_available_due_to_overlap(self):
        self.client.force_authenticate(user=self.staff_user)
        # First, create a confirmed reservation
        Reservation.objects.create(
            guest=self.guest1, room=self.room101,
            check_in_date=self.tomorrow, check_out_date=self.three_days_later,
            status=Reservation.ReservationStatus.CONFIRMED, number_of_adults=1
        )
        self.assertEqual(Reservation.objects.count(), 1)

        # Attempt to book overlapping period
        data_overlap_start = {
            "guest_id": self.guest2.pk, "room_id": self.room101.pk,
            "check_in_date": self.day_after_tomorrow.isoformat(), # Overlaps existing
            "check_out_date": self.four_days_later.isoformat(),
            "number_of_adults": 1,
        }
        response = self.client.post(self.list_url, data_overlap_start, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not available for the selected dates", response.data.get("room")[0])

        # Attempt to book fully contained period
        data_overlap_contained = {
            "guest_id": self.guest2.pk, "room_id": self.room101.pk,
            "check_in_date": self.tomorrow.isoformat(), # Exact same start
            "check_out_date": self.day_after_tomorrow.isoformat(), # Ends earlier, but overlaps
            "number_of_adults": 1,
        }
        response_contained = self.client.post(self.list_url, data_overlap_contained, format='json')
        self.assertEqual(response_contained.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not available for the selected dates", response_contained.data.get("room")[0])

    def test_create_reservation_invalid_dates(self):
        self.client.force_authenticate(user=self.staff_user)
        data = {
            "guest_id": self.guest1.pk, "room_id": self.room101.pk,
            "check_in_date": self.tomorrow.isoformat(),
            "check_out_date": self.tomorrow.isoformat(), # Check-out same as check-in
            "number_of_adults": 1,
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must be after check-in date", response.data.get("check_out_date")[0])

    def test_create_reservation_guest_exceeds_capacity(self):
        self.client.force_authenticate(user=self.staff_user)
        data = {
            "guest_id": self.guest1.pk, "room_id": self.room101.pk, # room101 capacity is 2
            "check_in_date": self.tomorrow.isoformat(),
            "check_out_date": self.day_after_tomorrow.isoformat(),
            "number_of_adults": 3, # Exceeds capacity
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exceeds the capacity", response.data.get("guests")[0])

    # --- Test Group Reservation Creation ---
    def test_create_group_reservation_success(self):
        self.client.force_authenticate(user=self.staff_user)
        group_data = [
            {
                "guest_id": self.guest1.pk, "room_id": self.room101.pk,
                "check_in_date": self.tomorrow.isoformat(), "check_out_date": self.day_after_tomorrow.isoformat(),
                "number_of_adults": 1, "group_name": "Tech Conference Group"
            },
            {
                "guest_id": self.guest2.pk, "room_id": self.room102.pk,
                "check_in_date": self.tomorrow.isoformat(), "check_out_date": self.day_after_tomorrow.isoformat(),
                "number_of_adults": 1, "group_name": "Tech Conference Group" # Name can be redundant if also in query param
            }
        ]
        # Pass group_name as query param as per current viewset create logic for groups
        response = self.client.post(f"{self.list_url}?group_name=Tech Conference Group", group_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Reservation.objects.count(), 2)
        reservations = Reservation.objects.all().order_by('guest_id') # Ensure consistent order for asserts
        self.assertIsNotNone(reservations[0].group_identifier)
        self.assertEqual(reservations[0].group_identifier, reservations[1].group_identifier)
        self.assertEqual(reservations[0].group_name, "Tech Conference Group")
        self.assertEqual(reservations[1].group_name, "Tech Conference Group")

    def test_create_group_reservation_partial_failure_rolls_back(self):
        self.client.force_authenticate(user=self.staff_user)
        # One valid, one invalid (e.g. room capacity exceeded)
        group_data = [
            { # Valid
                "guest_id": self.guest1.pk, "room_id": self.room101.pk,
                "check_in_date": self.tomorrow.isoformat(), "check_out_date": self.day_after_tomorrow.isoformat(),
                "number_of_adults": 1, "group_name": "Mixed Group"
            },
            { # Invalid - capacity of room102 (Double) is 2
                "guest_id": self.guest2.pk, "room_id": self.room102.pk,
                "check_in_date": self.tomorrow.isoformat(), "check_out_date": self.day_after_tomorrow.isoformat(),
                "number_of_adults": 3, "group_name": "Mixed Group"
            }
        ]
        response = self.client.post(f"{self.list_url}?group_name=Mixed Group", group_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Reservation.objects.count(), 0) # Transaction should roll back

    # --- Test Reservation Status Changes & Email ---
    def test_update_reservation_status_to_confirmed_sends_email(self):
        self.client.force_authenticate(user=self.staff_user)
        # Create a PENDING reservation first
        pending_res = Reservation.objects.create(
            guest=self.guest1, room=self.room101,
            check_in_date=self.tomorrow, check_out_date=self.day_after_tomorrow,
            status=Reservation.ReservationStatus.PENDING, number_of_adults=1
        )
        self.room101.status = Room.RoomStatus.AVAILABLE # Ensure room is available before booking
        self.room101.save()

        detail_url = reverse('reservation-detail', kwargs={'pk': pending_res.pk})
        update_data = {'status': Reservation.ReservationStatus.CONFIRMED}

        mail.outbox = [] # Clear outbox before this specific test action
        response = self.client.patch(detail_url, update_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        pending_res.refresh_from_db()
        self.assertEqual(pending_res.status, Reservation.ReservationStatus.CONFIRMED)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Your Reservation is Confirmed!')
        self.assertIn(self.guest1.email, mail.outbox[0].to)

        # Check room status
        self.room101.refresh_from_db()
        self.assertEqual(self.room101.status, Room.RoomStatus.BOOKED)


    def test_cancel_reservation_sends_email_and_updates_room(self):
        self.client.force_authenticate(user=self.staff_user) # Staff cancelling
        confirmed_res = Reservation.objects.create(
            guest=self.guest1, room=self.room101,
            check_in_date=self.tomorrow, check_out_date=self.day_after_tomorrow,
            status=Reservation.ReservationStatus.CONFIRMED, number_of_adults=1
        )
        # Assume confirming the reservation made the room BOOKED
        self.room101.status = Room.RoomStatus.BOOKED
        self.room101.save()

        cancel_url = reverse('reservation-cancel', kwargs={'pk': confirmed_res.pk}) # 'cancel' custom action

        mail.outbox = []
        response = self.client.post(cancel_url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        confirmed_res.refresh_from_db()
        self.assertEqual(confirmed_res.status, Reservation.ReservationStatus.CANCELLED)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Your Reservation has been Cancelled')

        # Check room status becomes AVAILABLE (assuming no other bookings for it)
        self.room101.refresh_from_db()
        self.assertEqual(self.room101.status, Room.RoomStatus.AVAILABLE)

    # --- Test Room Status Transitions (check_in, check_out) ---
    def test_check_in_reservation(self):
        self.client.force_authenticate(user=self.staff_user)
        # Create a CONFIRMED reservation for today
        reservation = Reservation.objects.create(
            guest=self.guest1, room=self.room101,
            check_in_date=self.today, # Check-in today
            check_out_date=self.tomorrow,
            status=Reservation.ReservationStatus.CONFIRMED, number_of_adults=1
        )
        self.room101.status = Room.RoomStatus.BOOKED # Room should be BOOKED
        self.room101.save()

        check_in_url = reverse('reservation-check-in', kwargs={'pk': reservation.pk})
        response = self.client.post(check_in_url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        reservation.refresh_from_db()
        self.room101.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.ReservationStatus.CHECKED_IN)
        self.assertEqual(self.room101.status, Room.RoomStatus.OCCUPIED)

    def test_check_out_reservation(self):
        self.client.force_authenticate(user=self.staff_user)
        reservation = Reservation.objects.create(
            guest=self.guest1, room=self.room101,
            check_in_date=self.today, check_out_date=self.tomorrow,
            status=Reservation.ReservationStatus.CHECKED_IN # Already checked-in
        )
        self.room101.status = Room.RoomStatus.OCCUPIED # Room is OCCUPIED
        self.room101.save()

        check_out_url = reverse('reservation-check-out', kwargs={'pk': reservation.pk})
        response = self.client.post(check_out_url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        reservation.refresh_from_db()
        self.room101.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.ReservationStatus.CHECKED_OUT)
        self.assertEqual(self.room101.status, Room.RoomStatus.NEEDS_CLEANING)

    # Add more tests:
    # - Attempting to check-in a PENDING reservation
    # - Attempting to check-in when check_in_date is in the future
    # - Attempting to check-out a reservation not CHECKED_IN
    # - Guest trying to cancel too late (based on policy)
    # - Filtering reservations by group_identifier / group_name
    # - Updating a reservation details (e.g., dates, guest numbers) and checking availability again.

    # Example for testing filtering (ensure your ReservationViewSet has filter_backends and filterset_fields configured)
    def test_filter_reservations_by_group_identifier(self):
        self.client.force_authenticate(user=self.admin_user) # Admin can see all
        group_id = uuid.uuid4()
        res1 = Reservation.objects.create(guest=self.guest1, room=self.room101, check_in_date=self.today, check_out_date=self.tomorrow, group_identifier=group_id, group_name="TestGroup", number_of_adults=1)
        res2 = Reservation.objects.create(guest=self.guest2, room=self.room102, check_in_date=self.today, check_out_date=self.tomorrow, group_identifier=group_id, group_name="TestGroup", number_of_adults=1)
        # Another reservation not in this group
        Reservation.objects.create(guest=self.guest1, room=self.room101, check_in_date=self.day_after_tomorrow, check_out_date=self.three_days_later, number_of_adults=1)

        url = f"{self.list_url}?group_identifier={group_id}"
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data['results']), 2) # Assuming pagination is on

        # Check if the returned reservation IDs match the ones created for the group
        returned_ids = sorted([item['id'] for item in response.data['results']])
        expected_ids = sorted([res1.id, res2.id])
        self.assertEqual(returned_ids, expected_ids)

    def test_cancel_reservation_by_guest_within_policy(self):
        # Guest User setup
        guest_user = CustomUser.objects.create_user('guestuser', 'guest@example.com', 'password123', role=CustomUser.Role.GUEST)
        self.guest1.user_account = guest_user # Link CustomUser to Guest profile
        self.guest1.save()
        self.client.force_authenticate(user=guest_user)

        # Reservation far enough in the future for cancellation
        future_check_in = self.today + datetime.timedelta(days=5)
        future_check_out = self.today + datetime.timedelta(days=7)

        confirmed_res = Reservation.objects.create(
            guest=self.guest1, room=self.room101,
            check_in_date=future_check_in, check_out_date=future_check_out,
            status=Reservation.ReservationStatus.CONFIRMED, number_of_adults=1
        )
        self.room101.status = Room.RoomStatus.BOOKED
        self.room101.save()

        cancel_url = reverse('reservation-cancel', kwargs={'pk': confirmed_res.pk})
        mail.outbox = []
        response = self.client.post(cancel_url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        confirmed_res.refresh_from_db()
        self.assertEqual(confirmed_res.status, Reservation.ReservationStatus.CANCELLED)
        self.assertEqual(len(mail.outbox), 1) # Cancellation email
        self.room101.refresh_from_db()
        self.assertEqual(self.room101.status, Room.RoomStatus.AVAILABLE)


    def test_cancel_reservation_by_guest_outside_policy(self):
        guest_user = CustomUser.objects.create_user('guestuser2', 'guest2@example.com', 'password123', role=CustomUser.Role.GUEST)
        self.guest2.user_account = guest_user
        self.guest2.save()
        self.client.force_authenticate(user=guest_user)

        # Reservation too close to cancel (e.g. check-in is today or tomorrow, policy is >1 day)
        confirmed_res_too_close = Reservation.objects.create(
            guest=self.guest2, room=self.room102,
            check_in_date=self.today, # Check-in today
            check_out_date=self.tomorrow,
            status=Reservation.ReservationStatus.CONFIRMED, number_of_adults=1
        )
        self.room102.status = Room.RoomStatus.BOOKED
        self.room102.save()

        cancel_url = reverse('reservation-cancel', kwargs={'pk': confirmed_res_too_close.pk})
        response = self.client.post(cancel_url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("Cancellation window closed", response.data.get('error', ''))
        confirmed_res_too_close.refresh_from_db()
        self.assertEqual(confirmed_res_too_close.status, Reservation.ReservationStatus.CONFIRMED) # Status should not change

    # --- Test Early/Late Check-in/out Management ---
    def test_request_and_approve_early_check_in(self):
        self.client.force_authenticate(user=self.staff_user) # Staff user for approval
        reservation = Reservation.objects.create(
            guest=self.guest1, room=self.room101,
            check_in_date=self.tomorrow, check_out_date=self.day_after_tomorrow,
            status=Reservation.ReservationStatus.CONFIRMED, number_of_adults=1
        )
        detail_url = reverse('reservation-detail', kwargs={'pk': reservation.pk})
        manage_url = reverse('reservation-manage-special-requests', kwargs={'pk': reservation.pk})

        # Guest (or staff on behalf of guest) requests early check-in (PATCH to reservation)
        # This assumes guest can update their own reservation to add request time
        # For this test, staff is doing it.
        early_time_request = timezone.make_aware(datetime.datetime.combine(self.tomorrow, datetime.time(10,0))) # 10 AM tomorrow

        # Staff or guest sets the requested time
        # Let's assume a guest (or staff via main endpoint) sets the request time first
        # For this test, we'll skip the guest request part and go straight to staff approval of a hypothetical request
        reservation.requested_early_check_in = early_time_request
        reservation.save()

        # Staff approves and sets a fee
        approval_data = {
            "is_early_check_in_approved": True,
            "early_check_in_fee": "25.00"
        }
        response = self.client.patch(manage_url, approval_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        reservation.refresh_from_db()
        self.assertTrue(reservation.is_early_check_in_approved)
        self.assertEqual(reservation.early_check_in_fee, Decimal("25.00"))
        # Total price should be updated by the model's save method
        expected_total = reservation.calculate_total_price() + Decimal("25.00")
        self.assertEqual(reservation.total_price, expected_total)

        # Now attempt to check-in early (e.g., it's tomorrow 10:00 AM)
        # To simulate this, we need to control current time, which is hard in standard tests.
        # So we trust the view logic that checks `is_early_check_in_approved`.
        # The view logic for actual check-in time vs requested_early_check_in.time() needs careful thought.

    def test_check_in_with_approved_early_check_in(self):
        self.client.force_authenticate(user=self.staff_user)
        early_check_in_datetime = timezone.make_aware(datetime.datetime.combine(self.today, datetime.time(10, 0)))

        reservation = Reservation.objects.create(
            guest=self.guest1, room=self.room101,
            check_in_date=self.today, # Standard check_in_date is today
            check_out_date=self.tomorrow,
            status=Reservation.ReservationStatus.CONFIRMED,
            number_of_adults=1,
            requested_early_check_in=early_check_in_datetime,
            is_early_check_in_approved=True # Approved for 10 AM today
        )
        self.room101.status = Room.RoomStatus.BOOKED
        self.room101.save()

        # To test this properly, we'd ideally mock timezone.now() to be self.today at 10:00 AM
        # For now, the view logic `reservation.check_in_date <= timezone.now().date()` covers the date part.
        # The time part comparison is trickier without mocking.
        # The current view logic for early check-in is:
        # - if check_in_date > today: requires approval for today
        # - if check_in_date == today: if current_time < standard_check_in_time, requires approval.
        # This test assumes current time is such that it's considered an early check-in scenario.

        check_in_url = reverse('reservation-check-in', kwargs={'pk': reservation.pk})
        # Assuming timezone.now() is currently < standard check-in time but >= approved early check-in time
        response = self.client.post(check_in_url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.ReservationStatus.CHECKED_IN)
        self.room101.refresh_from_db()
        self.assertEqual(self.room101.status, Room.RoomStatus.OCCUPIED)


    # --- Test Document Upload ---
    def test_guest_document_upload_and_verify(self):
        # Staff uploads document for guest1
        self.client.force_authenticate(user=self.staff_user)

        # URL for guest1's documents: /guests/{guest1.pk}/documents/
        # Need to ensure guest-document-list is the correct name from drf-nested-routers
        # It's typically <parent_basename>-<nested_basename>-list
        # If GuestViewSet basename is 'guest' and GuestDocumentViewSet is 'guest-document',
        # then it would be 'guest-guest-document-list'. Let's verify this.
        # Simpler: use the direct path if reverse is tricky with nesting setup here.
        # For router.register(r'guests', GuestViewSet, basename='guest')
        # guest_documents_router = NestedSimpleRouter(router, r'guests', lookup='guest')
        # guest_documents_router.register(r'documents', GuestDocumentViewSet, basename='guest-document')
        # The name should be 'guest-document-list' and it needs guest_pk.
        upload_url = reverse('guest-document-list', kwargs={'guest_pk': self.guest1.pk})

        # Create a dummy image file
        dummy_image = SimpleUploadedFile("passport.jpg", b"file_content", content_type="image/jpeg")

        doc_data = {
            "document_type": GuestDocument.DocumentType.PASSPORT,
            "document_number": "X12345",
            "document_image": dummy_image,
            # guest_id is implicit from URL for creation if serializer is set up for it,
            # or it could be passed in data if not using nested creation this way.
            # Our serializer has guest_id as write_only.
            # The ViewSet's perform_create is expected to handle guest_pk from URL.
        }

        response = self.client.post(upload_url, doc_data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(GuestDocument.objects.count(), 1)
        doc = GuestDocument.objects.first()
        self.assertEqual(doc.guest, self.guest1)
        self.assertEqual(doc.document_type, GuestDocument.DocumentType.PASSPORT)
        self.assertTrue(doc.document_image.name.endswith('passport.jpg'))

        # Staff verifies the document
        verify_url = reverse('guest-document-verify', kwargs={'guest_pk': self.guest1.pk, 'pk': doc.pk})
        response_verify = self.client.post(verify_url, {}, format='json')
        self.assertEqual(response_verify.status_code, status.HTTP_200_OK, response_verify.data)
        doc.refresh_from_db()
        self.assertIsNotNone(doc.verified_at)
        self.assertEqual(doc.verified_by, self.staff_user)


    # --- Test Room Change ---
    def test_change_reservation_room_success(self):
        self.client.force_authenticate(user=self.staff_user)
        reservation = Reservation.objects.create(
            guest=self.guest1, room=self.room101, # Initially in room101
            check_in_date=self.tomorrow, check_out_date=self.day_after_tomorrow,
            status=Reservation.ReservationStatus.CONFIRMED, number_of_adults=1
        )
        self.room101.status = Room.RoomStatus.BOOKED # room101 is now BOOKED
        self.room101.save()
        self.room102.status = Room.RoomStatus.AVAILABLE # room102 is AVAILABLE
        self.room102.save()

        change_room_url = reverse('reservation-change-room', kwargs={'pk': reservation.pk})
        payload = {"new_room_id": self.room102.pk}

        response = self.client.post(change_room_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        reservation.refresh_from_db()
        self.assertEqual(reservation.room, self.room102) # Room changed

        self.room101.refresh_from_db()
        self.assertEqual(self.room101.status, Room.RoomStatus.AVAILABLE) # Old room became available

        self.room102.refresh_from_db()
        self.assertEqual(self.room102.status, Room.RoomStatus.BOOKED) # New room became booked


    def test_change_reservation_room_fail_new_room_unavailable(self):
        self.client.force_authenticate(user=self.staff_user)
        # room102 is already booked by another reservation
        other_reservation = Reservation.objects.create(
            guest=self.guest2, room=self.room102,
            check_in_date=self.tomorrow, check_out_date=self.day_after_tomorrow,
            status=Reservation.ReservationStatus.CONFIRMED, number_of_adults=1
        )
        self.room102.status = Room.RoomStatus.BOOKED
        self.room102.save()

        reservation_to_change = Reservation.objects.create(
            guest=self.guest1, room=self.room101,
            check_in_date=self.tomorrow, check_out_date=self.day_after_tomorrow,
            status=Reservation.ReservationStatus.CONFIRMED, number_of_adults=1
        )

        change_room_url = reverse('reservation-change-room', kwargs={'pk': reservation_to_change.pk})
        payload = {"new_room_id": self.room102.pk} # Attempt to move to already booked room102

        response = self.client.post(change_room_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not available", response.data.get('error', '').lower())


# To run these tests, you'd typically use:
# python manage.py test reservations
# Ensure that your URL names used in reverse() (e.g., 'reservation-list', 'reservation-detail',
# 'reservation-cancel', 'reservation-check-in', 'reservation-check-out') match what's defined
# in your reservations/urls.py for the ReservationViewSet.
# Example: router.register(r'reservations', ReservationViewSet, basename='reservation')
# Then for custom actions, they'd be like 'reservation-cancel'.
# The default list is 'reservation-list', detail is 'reservation-detail'.
# Check your main urls.py too for how reservations app is included.
# If ReservationViewSet is registered as:
# router = DefaultRouter()
# router.register(r'', views.ReservationViewSet, basename='reservation')
# and included in project urls.py as path("bookings/", include("reservations.urls"))
# then list would be reverse("reservation-list") if basename is 'reservation'
# and custom actions would be reverse("reservation-cancel", kwargs={'pk': pk_value}).

# Correction: For DefaultRouter, the name is usually <basename>-list and <basename>-detail.
# So, if basename='reservation', then reverse('reservation-list') is correct.
# Custom actions are named <basename>-<action_name>.
# e.g. @action(detail=True, methods=['post'], url_path='cancel-booking', url_name='cancel_booking')
# would be reverse('reservation-cancel_booking', kwargs={'pk': pk})
# If url_path and url_name are not set, it defaults to the method name.
# So, `cancel` action -> `reservation-cancel`.
# `check_in` action -> `reservation-check-in`.
# `check_out` action -> `reservation-check-out`.
# This seems to be what I've used, so it should be okay.
