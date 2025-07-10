import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import reservationService from '../services/reservation.service'; // Assuming you have this

const ReservationDetailPage = () => {
  const { id } = useParams();
  const [reservation, setReservation] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // State for action processing
  const [isLoadingAction, setIsLoadingAction] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');

  const fetchReservationDetails = () => {
    setIsLoading(true);
    setError('');
    setActionError('');
    setActionSuccess('');
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
  };

  useEffect(() => {
    if (id) {
      fetchReservationDetails();
    }
  }, [id]); // Re-fetch if ID changes (though typically it won't for a detail page)

  const handleAction = async (actionPromise, successMessage) => {
    setIsLoadingAction(true);
    setActionError('');
    setActionSuccess('');
    try {
      await actionPromise;
      setActionSuccess(successMessage);
      fetchReservationDetails(); // Refresh data after action
    } catch (err) {
      setActionError(err.response?.data?.detail || err.response?.data?.error || err.message || 'Action failed.');
      console.error("Action error:", err);
    } finally {
      setIsLoadingAction(false);
    }
  };

  const handleCheckIn = () => {
    handleAction(
      reservationService.checkInReservation(id),
      'Guest checked-in successfully.'
    );
  };

  const handleCheckOut = () => {
    handleAction(
      reservationService.checkOutReservation(id),
      'Guest checked-out successfully.'
    );
  };

  const handleCancelReservation = () => {
    if (window.confirm('Are you sure you want to cancel this reservation?')) {
      handleAction(
        reservationService.cancelReservation(id),
        'Reservation cancelled successfully.'
      );
    }
  };

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
      </div>

      <div style={{ marginTop: '30px', borderTop: '1px solid #eee', paddingTop: '20px' }}>
        <h3>Actions</h3>
        {/* Conditional rendering of action buttons based on reservation status */}
        {reservation.status === 'CONFIRMED' && (
          <button
            onClick={handleCheckIn}
            disabled={isLoadingAction}
            style={{ marginRight: '10px', backgroundColor: 'green', color: 'white' }}
          >
            {isLoadingAction ? 'Processing...' : 'Check-in Guest'}
          </button>
        )}
        {reservation.status === 'CHECKED_IN' && (
          <button
            onClick={handleCheckOut}
            disabled={isLoadingAction}
            style={{ marginRight: '10px', backgroundColor: 'orange', color: 'white' }}
          >
            {isLoadingAction ? 'Processing...' : 'Check-out Guest'}
          </button>
        )}
        {(reservation.status === 'PENDING' || reservation.status === 'CONFIRMED') && (
          <button
            onClick={handleCancelReservation}
            disabled={isLoadingAction}
            style={{ marginRight: '10px', backgroundColor: 'red', color: 'white' }}
          >
            {isLoadingAction ? 'Processing...' : 'Cancel Reservation'}
          </button>
        )}
         {/* TODO: Add Change Room and Manage Special Requests buttons if applicable */}
        {actionError && <p style={{ color: 'red', marginTop: '10px' }}>Error: {actionError}</p>}
        {actionSuccess && <p style={{ color: 'green', marginTop: '10px' }}>{actionSuccess}</p>}
      </div>
    </div>
  );
};

export default ReservationDetailPage;
