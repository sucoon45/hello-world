import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import reservationService from '../services/reservation.service'; // Assuming you have this

const ReservationDetailPage = () => {
  const { id } = useParams(); // Get reservation ID from URL
  const [reservation, setReservation] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (id) {
      setIsLoading(true);
      reservationService.getReservationById(id)
        .then(data => {
          setReservation(data);
          setIsLoading(false);
        })
        .catch(err => {
          setError(`Failed to fetch reservation details for ID ${id}.`);
          setIsLoading(false);
          console.error(err);
        });
    }
  }, [id]);

  if (isLoading) {
    return <p>Loading reservation details...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  if (!reservation) {
    return <p>Reservation not found.</p>;
  }

  return (
    <div>
      <h1>Reservation Details: #{reservation.id}</h1>
      <p><strong>Invoice Number:</strong> {reservation.invoice_number || 'N/A'}</p>
      <p><strong>Guest:</strong> {reservation.guest?.first_name} {reservation.guest?.last_name} ({reservation.guest?.email})</p>
      <p><strong>Room:</strong> {reservation.room?.room_number} ({reservation.room?.room_type})</p>
      <p><strong>Check-in:</strong> {new Date(reservation.check_in_date).toLocaleDateString()}</p>
      <p><strong>Check-out:</strong> {new Date(reservation.check_out_date).toLocaleDateString()}</p>
      <p><strong>Status:</strong> {reservation.status_display || reservation.status}</p>
      <p><strong>Adults:</strong> {reservation.number_of_adults}</p>
      <p><strong>Children:</strong> {reservation.number_of_children}</p>
      <p><strong>Total Price:</strong> ${reservation.total_price}</p>
      <p><strong>Notes:</strong> {reservation.notes || 'N/A'}</p>

      {reservation.group_name && <p><strong>Group Name:</strong> {reservation.group_name}</p>}
      {reservation.group_identifier && <p><strong>Group ID:</strong> {reservation.group_identifier}</p>}

      <h3>Special Requests</h3>
      <p><strong>Requested Early Check-in:</strong> {reservation.requested_early_check_in ? new Date(reservation.requested_early_check_in).toLocaleString() : 'N/A'}</p>
      <p><strong>Early Check-in Approved:</strong> {reservation.is_early_check_in_approved ? 'Yes' : 'No'}</p>
      {reservation.is_early_check_in_approved && <p><strong>Early Check-in Fee:</strong> ${reservation.early_check_in_fee || '0.00'}</p>}

      <p><strong>Requested Late Check-out:</strong> {reservation.requested_late_check_out ? new Date(reservation.requested_late_check_out).toLocaleString() : 'N/A'}</p>
      <p><strong>Late Check-out Approved:</strong> {reservation.is_late_check_out_approved ? 'Yes' : 'No'}</p>
      {reservation.is_late_check_out_approved && <p><strong>Late Check-out Fee:</strong> ${reservation.late_check_out_fee || '0.00'}</p>}

      <div style={{ marginTop: '20px' }}>
        <Link to={`/app/reservations/${id}/edit`} style={{ marginRight: '10px' }}>
          <button>Edit Reservation</button>
        </Link>
        <Link to="/app/reservations">
          <button>Back to List</button>
        </Link>
        {/* Add buttons for Check-in, Check-out, Cancel actions here, calling reservationService */}
      </div>
    </div>
  );
};

export default ReservationDetailPage;
