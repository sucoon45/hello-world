import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
// import reservationService from '../services/reservation.service';
// import guestService from '../services/guest.service'; // For fetching guests
// import roomService from '../services/room.service';   // For fetching rooms

const ReservationFormPage = () => {
  const { id } = useParams(); // For edit mode
  const navigate = useNavigate();
  const isEditMode = Boolean(id);

  const [formData, setFormData] = useState({
    guest_id: '',
    room_id: '',
    check_in_date: '',
    check_out_date: '',
    number_of_adults: 1,
    number_of_children: 0,
    status: 'PENDING', // Default status for new reservations
    notes: '',
    // Add fields for early/late check-in requests if applicable on form
    // requested_early_check_in: null,
    // requested_late_check_out: null,
  });
  const [guests, setGuests] = useState([]); // To populate guest dropdown
  const [rooms, setRooms] = useState([]);   // To populate room dropdown
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // Fetch guests and rooms for dropdowns
    // setIsLoading(true);
    // Promise.all([
    //   guestService.getAllGuests({ page_size: 1000 }), // Fetch all guests, or implement search
    //   roomService.getAllRooms({ status: 'AVAILABLE', page_size: 1000 }) // Fetch available rooms
    // ]).then(([guestRes, roomRes]) => {
    //   setGuests(guestRes.data.results || guestRes.data);
    //   setRooms(roomRes.data.results || roomRes.data);
    //   setIsLoading(false);
    // }).catch(err => {
    //   setError('Failed to load initial data (guests/rooms).');
    //   setIsLoading(false);
    // });

    if (isEditMode) {
      // Fetch reservation details if in edit mode
      // setIsLoading(true);
      // reservationService.getReservationById(id)
      //   .then(data => {
      //     setFormData({
      //       guest_id: data.guest.id,
      //       room_id: data.room.id,
      //       check_in_date: data.check_in_date,
      //       check_out_date: data.check_out_date,
      //       number_of_adults: data.number_of_adults,
      //       number_of_children: data.number_of_children,
      //       status: data.status,
      //       notes: data.notes || '',
      //     });
      //     setIsLoading(false);
      //   })
      //   .catch(err => {
      //     setError(`Failed to fetch reservation ${id} for editing.`);
      //     setIsLoading(false);
      //   });
      console.log(`Edit mode for reservation ID: ${id}. Fetching data (placeholder).`);
    }
    console.log("ReservationFormPage mounted. API calls for guests, rooms, and existing reservation data (if edit) will be implemented here.");
  }, [id, isEditMode]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    // setIsLoading(true);
    // setError('');
    // try {
    //   let response;
    //   const payload = { ...formData };
    //   // Convert date strings if necessary, ensure numbers are numbers
    //   payload.number_of_adults = parseInt(payload.number_of_adults, 10);
    //   payload.number_of_children = parseInt(payload.number_of_children, 10);

    //   if (isEditMode) {
    //     response = await reservationService.updateReservation(id, payload);
    //   } else {
    //     response = await reservationService.createReservation(payload);
    //   }
    //   navigate(`/app/reservations/${response.data.id || id}`); // Go to detail page
    // } catch (err) {
    //   setError(err.response?.data?.detail || err.message || (isEditMode ? 'Failed to update reservation.' : 'Failed to create reservation.'));
    // } finally {
    //   setIsLoading(false);
    // }
    alert(`Form submitted (placeholder). Data: ${JSON.stringify(formData)}`);
  };

  if (isLoading && isEditMode) { // Only show loading for edit mode initial fetch for now
      return <p>Loading reservation data for editing...</p>;
  }

  return (
    <div>
      <h1>{isEditMode ? 'Edit Reservation' : 'Create New Reservation'}</h1>
      <form onSubmit={handleSubmit}>
        {/* Basic Form Fields - To be enhanced with dropdowns for Guest/Room, DatePickers */}
        <div>
          <label htmlFor="guest_id">Guest:</label>
          <input type="text" name="guest_id" id="guest_id" value={formData.guest_id} onChange={handleChange} placeholder="Guest ID (select later)" required />
          {/* Replace with:
          <select name="guest_id" value={formData.guest_id} onChange={handleChange} required>
            <option value="">Select Guest</option>
            {guests.map(g => <option key={g.id} value={g.id}>{g.first_name} {g.last_name}</option>)}
          </select>
          */}
        </div>
        <div>
          <label htmlFor="room_id">Room:</label>
          <input type="text" name="room_id" id="room_id" value={formData.room_id} onChange={handleChange} placeholder="Room ID (select later)" required />
           {/* Replace with:
          <select name="room_id" value={formData.room_id} onChange={handleChange} required>
            <option value="">Select Room</option>
            {rooms.map(r => <option key={r.id} value={r.id}>{r.room_number} ({r.room_type_name})</option>)}
          </select>
          */}
        </div>
        <div>
          <label htmlFor="check_in_date">Check-in Date:</label>
          <input type="date" name="check_in_date" id="check_in_date" value={formData.check_in_date} onChange={handleChange} required />
        </div>
        <div>
          <label htmlFor="check_out_date">Check-out Date:</label>
          <input type="date" name="check_out_date" id="check_out_date" value={formData.check_out_date} onChange={handleChange} required />
        </div>
        <div>
          <label htmlFor="number_of_adults">Adults:</label>
          <input type="number" name="number_of_adults" id="number_of_adults" value={formData.number_of_adults} onChange={handleChange} min="1" required />
        </div>
        <div>
          <label htmlFor="number_of_children">Children:</label>
          <input type="number" name="number_of_children" id="number_of_children" value={formData.number_of_children} onChange={handleChange} min="0" required />
        </div>
        <div>
          <label htmlFor="status">Status:</label>
          <select name="status" id="status" value={formData.status} onChange={handleChange}>
            <option value="PENDING">Pending</option>
            <option value="CONFIRMED">Confirmed</option>
            {/* Other statuses might be set via actions, not directly on form always */}
          </select>
        </div>
        <div>
          <label htmlFor="notes">Notes:</label>
          <textarea name="notes" id="notes" value={formData.notes} onChange={handleChange}></textarea>
        </div>

        {error && <p style={{color: 'red'}}>{error}</p>}
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving...' : (isEditMode ? 'Update Reservation' : 'Create Reservation')}
        </button>
        <button type="button" onClick={() => navigate('/app/reservations')} style={{marginLeft: '10px'}}>
          Cancel
        </button>
      </form>
    </div>
  );
};

export default ReservationFormPage;
