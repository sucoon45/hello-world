import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import reservationService from '../services/reservation.service';
import guestService from '../services/guest.service';
import roomService from '../services/room.service';

const ReservationFormPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEditMode = Boolean(id);

  const initialFormData = {
    guest_id: '', // Will store guest PK
    room_id: '',   // Will store room PK
    check_in_date: '',
    check_out_date: '',
    number_of_adults: 1,
    number_of_children: 0,
    status: 'PENDING',
    notes: '',
    group_name: '', // For group bookings
    // For early/late check-in requests (optional on this form, could be separate management)
    requested_early_check_in: '', // Expects ISO datetime string or null
    requested_late_check_out: '',  // Expects ISO datetime string or null
  };

  const [formData, setFormData] = useState(initialFormData);
  const [guests, setGuests] = useState([]);
  const [rooms, setRooms] = useState([]);   // For room dropdown (all rooms initially, or filtered available)
  const [roomTypes, setRoomTypes] = useState([]); // For potentially filtering rooms by type first
  const [selectedRoomType, setSelectedRoomType] = useState('');

  const [isLoading, setIsLoading] = useState(false); // General loading for page data
  const [isSubmitting, setIsSubmitting] = useState(false); // For form submission
  const [error, setError] = useState('');
  const [formErrors, setFormErrors] = useState({}); // For field-specific errors from backend

  useEffect(() => {
    const loadInitialData = async () => {
      setIsLoading(true);
      try {
        const guestPromise = guestService.getAllGuests({ page_size: 1000 }); // Fetch many guests
        const roomTypePromise = roomService.getAllRoomTypes({ page_size: 100 }); // Fetch room types
        // Fetch all rooms for now, or implement more complex availability filtering later
        const roomPromise = roomService.getAllRooms({ page_size: 1000 /* status: 'AVAILABLE' */ });

        const [guestRes, roomTypeRes, roomRes] = await Promise.all([guestPromise, roomTypePromise, roomPromise]);

        setGuests(guestRes.results || guestRes); // Adjust based on actual response structure
        setRoomTypes(roomTypeRes.results || roomTypeRes);
        setRooms(roomRes.results || roomRes);

        if (isEditMode && id) {
          const reservationData = await reservationService.getReservationById(id);
          setFormData({
            guest_id: reservationData.guest?.id || '', // guest object might contain id, or guest might be just an ID
            room_id: reservationData.room?.id || '',   // room object might contain id
            check_in_date: reservationData.check_in_date || '',
            check_out_date: reservationData.check_out_date || '',
            number_of_adults: reservationData.number_of_adults || 1,
            number_of_children: reservationData.number_of_children || 0,
            status: reservationData.status || 'PENDING',
            notes: reservationData.notes || '',
            group_name: reservationData.group_name || '',
            requested_early_check_in: reservationData.requested_early_check_in ? reservationData.requested_early_check_in.substring(0, 16) : '', // Format for datetime-local
            requested_late_check_out: reservationData.requested_late_check_out ? reservationData.requested_late_check_out.substring(0, 16) : '', // Format for datetime-local
          });
          // If room_type was part of reservationData or room data, could set selectedRoomType
          if (reservationData.room?.room_type_id) { // Assuming room_type_id is available
            setSelectedRoomType(reservationData.room.room_type_id.toString());
          } else if (reservationData.room?.room_type?.id) {
            setSelectedRoomType(reservationData.room.room_type.id.toString());
          }
        }
      } catch (err) {
        console.error("Failed to load initial data for form:", err);
        setError("Failed to load necessary data. Please try again.");
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialData();
  }, [id, isEditMode]);

  // Filter rooms based on selected room type
  const filteredRooms = selectedRoomType
    ? rooms.filter(room => room.room_type_id === parseInt(selectedRoomType) || room.room_type === parseInt(selectedRoomType) || room.room_type.id === parseInt(selectedRoomType))
    : rooms;


  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : (type === 'number' ? parseInt(value, 10) : value),
    }));
  };

  const handleRoomTypeChange = (e) => {
    setSelectedRoomType(e.target.value);
    setFormData(prev => ({ ...prev, room_id: '' })); // Reset room selection when type changes
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');
    setFormErrors({});

    // Prepare payload, ensure empty strings for dates/datetimes are null for backend
    const payload = { ...formData };
    if (!payload.requested_early_check_in) delete payload.requested_early_check_in; else payload.requested_early_check_in = `${payload.requested_early_check_in}:00`; // Add seconds if needed by backend
    if (!payload.requested_late_check_out) delete payload.requested_late_check_out; else payload.requested_late_check_out = `${payload.requested_late_check_out}:00`;
    if (!payload.group_name) delete payload.group_name;


    try {
      let response;
      if (isEditMode) {
        response = await reservationService.updateReservation(id, payload);
      } else {
        response = await reservationService.createReservation(payload);
      }
      navigate(`/app/reservations/${response.id || id}`);
    } catch (err) {
      console.error("Form submission error:", err.response || err);
      if (err.response && err.response.data && typeof err.response.data === 'object') {
        // Handle DRF validation errors (field-specific)
        setFormErrors(err.response.data);
        setError("Please correct the errors below.");
      } else {
        setError(err.message || (isEditMode ? 'Failed to update reservation.' : 'Failed to create reservation.'));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
      return <p>Loading form data...</p>;
  }

  return (
    <div style={{ padding: '20px' }}>
      <h1>{isEditMode ? `Edit Reservation #${id}` : 'Create New Reservation'}</h1>
      {error && <p style={{color: 'red', fontWeight: 'bold'}}>{error}</p>}

      <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

        {/* Column 1 */}
        <div>
          <div>
            <label htmlFor="guest_id">Guest:</label>
            <select name="guest_id" id="guest_id" value={formData.guest_id} onChange={handleChange} required>
              <option value="">Select Guest</option>
              {guests.map(g => <option key={g.id} value={g.id}>{g.first_name} {g.last_name} ({g.email})</option>)}
            </select>
            {formErrors.guest_id && <p style={{color: 'red'}}>{formErrors.guest_id}</p>}
          </div>

          <div>
            <label htmlFor="roomTypeFilter">Room Type:</label>
            <select id="roomTypeFilter" value={selectedRoomType} onChange={handleRoomTypeChange}>
              <option value="">All Room Types</option>
              {roomTypes.map(rt => <option key={rt.id} value={rt.id}>{rt.name}</option>)}
            </select>
          </div>

          <div>
            <label htmlFor="room_id">Room:</label>
            <select name="room_id" id="room_id" value={formData.room_id} onChange={handleChange} required disabled={!selectedRoomType && !isEditMode && rooms.length > 0}>
              <option value="">{selectedRoomType ? 'Select Room' : (rooms.length > 0 ? 'Select Room Type First' : 'No Rooms Available')}</option>
              {filteredRooms.map(r => <option key={r.id} value={r.id}>{r.room_number} ({r.room_type}) - ${r.current_effective_price || r.price_per_night}</option>)}
            </select>
            {formErrors.room_id && <p style={{color: 'red'}}>{formErrors.room_id}</p>}
          </div>

          <div>
            <label htmlFor="check_in_date">Check-in Date:</label>
            <input type="date" name="check_in_date" id="check_in_date" value={formData.check_in_date} onChange={handleChange} required />
            {formErrors.check_in_date && <p style={{color: 'red'}}>{formErrors.check_in_date}</p>}
          </div>

          <div>
            <label htmlFor="check_out_date">Check-out Date:</label>
            <input type="date" name="check_out_date" id="check_out_date" value={formData.check_out_date} onChange={handleChange} required />
            {formErrors.check_out_date && <p style={{color: 'red'}}>{formErrors.check_out_date}</p>}
          </div>
        </div>

        {/* Column 2 */}
        <div>
          <div>
            <label htmlFor="number_of_adults">Adults:</label>
            <input type="number" name="number_of_adults" id="number_of_adults" value={formData.number_of_adults} onChange={handleChange} min="1" required />
            {formErrors.number_of_adults && <p style={{color: 'red'}}>{formErrors.number_of_adults}</p>}
          </div>

          <div>
            <label htmlFor="number_of_children">Children:</label>
            <input type="number" name="number_of_children" id="number_of_children" value={formData.number_of_children} onChange={handleChange} min="0" />
            {formErrors.number_of_children && <p style={{color: 'red'}}>{formErrors.number_of_children}</p>}
          </div>

          <div>
            <label htmlFor="status">Status:</label>
            <select name="status" id="status" value={formData.status} onChange={handleChange}>
              <option value="PENDING">Pending</option>
              <option value="CONFIRMED">Confirmed</option>
              {isEditMode && <option value="CHECKED_IN">Checked-In</option>}
              {isEditMode && <option value="CHECKED_OUT">Checked-Out</option>}
              {isEditMode && <option value="CANCELLED">Cancelled</option>}
              {isEditMode && <option value="NO_SHOW">No Show</option>}
            </select>
            {formErrors.status && <p style={{color: 'red'}}>{formErrors.status}</p>}
          </div>

          <div>
            <label htmlFor="group_name">Group Name (Optional):</label>
            <input type="text" name="group_name" id="group_name" value={formData.group_name} onChange={handleChange} />
            {formErrors.group_name && <p style={{color: 'red'}}>{formErrors.group_name}</p>}
          </div>

          <div>
            <label htmlFor="notes">Notes:</label>
            <textarea name="notes" id="notes" value={formData.notes} onChange={handleChange} rows="3"></textarea>
            {formErrors.notes && <p style={{color: 'red'}}>{formErrors.notes}</p>}
          </div>
        </div>

        {/* Spanning across two columns for special requests */}
        <div style={{ gridColumn: '1 / -1' }}>
          <h4>Special Requests (Optional)</h4>
          <div>
            <label htmlFor="requested_early_check_in">Requested Early Check-in Time:</label>
            <input type="datetime-local" name="requested_early_check_in" id="requested_early_check_in" value={formData.requested_early_check_in} onChange={handleChange} />
            {formErrors.requested_early_check_in && <p style={{color: 'red'}}>{formErrors.requested_early_check_in}</p>}
          </div>
          <div>
            <label htmlFor="requested_late_check_out">Requested Late Check-out Time:</label>
            <input type="datetime-local" name="requested_late_check_out" id="requested_late_check_out" value={formData.requested_late_check_out} onChange={handleChange} />
            {formErrors.requested_late_check_out && <p style={{color: 'red'}}>{formErrors.requested_late_check_out}</p>}
          </div>
        </div>

        {/* Submission and general errors */}
        {formErrors.non_field_errors && <p style={{color: 'red', gridColumn: '1 / -1'}}>{formErrors.non_field_errors}</p>}
        {formErrors.detail && <p style={{color: 'red', gridColumn: '1 / -1'}}>{formErrors.detail}</p>}


        <div style={{ gridColumn: '1 / -1', marginTop: '20px' }}>
          <button type="submit" disabled={isSubmitting || isLoading} style={{padding: '10px 15px'}}>
            {isSubmitting ? 'Saving...' : (isEditMode ? 'Update Reservation' : 'Create Reservation')}
          </button>
          <button type="button" onClick={() => navigate(isEditMode ? `/app/reservations/${id}` : '/app/reservations')} style={{marginLeft: '10px', padding: '10px 15px'}}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
};

export default ReservationFormPage;
