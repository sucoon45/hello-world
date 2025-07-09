import React, { useState, useEffect } from 'react';
// import reservationService from '../services/reservation.service'; // To be created
// import { Link } from 'react-router-dom';

const ReservationsListPage = () => {
  const [reservations, setReservations] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // Placeholder for fetching reservations
    // setIsLoading(true);
    // reservationService.getAllReservations()
    //   .then(response => {
    //     setReservations(response.data.results || response.data); // Adjust based on API response structure
    //     setIsLoading(false);
    //   })
    //   .catch(err => {
    //     setError('Failed to fetch reservations.');
    //     setIsLoading(false);
    //     console.error(err);
    //   });
    console.log("ReservationsListPage mounted. API call to fetch reservations will be implemented here.");
  }, []);

  if (isLoading) {
    return <p>Loading reservations...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div>
      <h1>Reservations Management</h1>
      <div style={{ marginBottom: '20px' }}>
        {/* <Link to="/app/reservations/new">
          <button>Create New Reservation</button>
        </Link> */}
        <p><i>(Search/filter controls will go here)</i></p>
      </div>

      {reservations.length === 0 && !isLoading ? (
        <p>No reservations found. (Or API not yet implemented)</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Guest</th>
              <th>Room</th>
              <th>Check-in</th>
              <th>Check-out</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {/* Placeholder for reservation rows - mapping will go here */}
            {/* Example row structure:
            {reservations.map(res => (
              <tr key={res.id}>
                <td>{res.id}</td>
                <td>{res.guest?.first_name} {res.guest?.last_name}</td>
                <td>{res.room?.room_number}</td>
                <td>{res.check_in_date}</td>
                <td>{res.check_out_date}</td>
                <td>{res.status_display || res.status}</td>
                <td>
                  <Link to={`/app/reservations/${res.id}`}>View</Link> |
                  <Link to={`/app/reservations/${res.id}/edit`}>Edit</Link>
                </td>
              </tr>
            ))}
            */}
            <tr>
              <td colSpan="7"><i>Reservation data will be displayed here once API is connected.</i></td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
};

export default ReservationsListPage;
