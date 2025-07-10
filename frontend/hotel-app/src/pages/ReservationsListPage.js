import React, { useState, useEffect } from 'react';
import reservationService from '../services/reservation.service';
import { Link } from 'react-router-dom'; // For action links

const ReservationsListPage = () => {
  const [reservations, setReservations] = useState([]);
  const [isLoading, setIsLoading] = useState(true); // Start with loading true
  const [error, setError] = useState('');

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  // const itemsPerPage = 10; // Or get from API/settings if backend controls this via PageNumberPagination

  // Filter state
  const [statusFilter, setStatusFilter] = useState('');
  const [checkInDateFromFilter, setCheckInDateFromFilter] = useState('');
  const [checkInDateToFilter, setCheckInDateToFilter] = useState('');
  const [guestEmailFilter, setGuestEmailFilter] = useState('');


  const fetchReservations = async (page, filters = {}) => {
    setIsLoading(true);
    setError('');
    try {
      const params = {
        page: page,
        ...(filters.status && { status: filters.status }),
        ...(filters.check_in_date_after && { check_in_date__gte: filters.check_in_date_after }),
        ...(filters.check_in_date_before && { check_in_date__lte: filters.check_in_date_before }),
        ...(filters.guest_email && { search: filters.guest_email }), // Use 'search' for guest email, assuming backend search_fields includes it
        // Add other filters like room_id, etc. as needed
      };

      const data = await reservationService.getAllReservations(params);
      setReservations(data.results || []);
      setTotalCount(data.count || 0);
      // Calculate total pages: (assuming backend doesn't directly provide total_pages)
      // If backend uses Django Rest Framework's PageNumberPagination, it might send 'count'.
      // Page size is set in DRF settings (e.g., PAGE_SIZE = 10).
      // We need to know the page size to calculate totalPages correctly.
      // For now, let's assume a fixed page size or wait for backend to return total_pages if available.
      // If DRF settings PAGE_SIZE = 10, then:
      if (data.count && data.results.length > 0) { // Check if results is not empty to avoid division by zero with some page size settings
        const pageSize = process.env.REACT_APP_PAGE_SIZE || 10; // Get page size from env or default
        setTotalPages(Math.ceil(data.count / pageSize));
      } else if (data.count === 0) {
        setTotalPages(0);
      }

    } catch (err) {
      setError('Failed to fetch reservations. Please try again later.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Construct filters object from state
    const currentFilters = {
      status: statusFilter,
      check_in_date_after: checkInDateFromFilter,
      check_in_date_before: checkInDateToFilter,
      guest_email: guestEmailFilter,
    };
    fetchReservations(currentPage, currentFilters);
  }, [currentPage, statusFilter, checkInDateFromFilter, checkInDateToFilter, guestEmailFilter]); // Refetch when page or any filter changes

  const handleApplyFilters = () => {
    setCurrentPage(1); // Reset to first page when filters are applied
    // useEffect will then pick up the new filter values and refetch
    // No need to call fetchReservations directly here if filters are in dependency array of useEffect.
    // However, if we want an explicit button click to trigger fetch, we could call it:
    // const currentFilters = { status: statusFilter, ... };
    // fetchReservations(1, currentFilters);
  };

  const handleClearFilters = () => {
    setStatusFilter('');
    setCheckInDateFromFilter('');
    setCheckInDateToFilter('');
    setGuestEmailFilter('');
    setCurrentPage(1); // Reset to first page
    // useEffect will refetch with cleared filters
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  if (isLoading) {
    return <p>Loading reservations...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div>
      <h1>Reservations Management</h1>

      {/* Filter Section */}
      <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #eee' }}>
        <h4>Filters</h4>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <label htmlFor="statusFilter" style={{ marginRight: '5px' }}>Status:</label>
            <select id="statusFilter" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All</option>
              <option value="PENDING">Pending</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="CHECKED_IN">Checked-In</option>
              <option value="CHECKED_OUT">Checked-Out</option>
              <option value="CANCELLED">Cancelled</option>
              <option value="NO_SHOW">No Show</option>
            </select>
          </div>
          <div>
            <label htmlFor="checkInFrom" style={{ marginRight: '5px' }}>Check-in From:</label>
            <input type="date" id="checkInFrom" value={checkInDateFromFilter} onChange={e => setCheckInDateFromFilter(e.target.value)} />
          </div>
          <div>
            <label htmlFor="checkInTo" style={{ marginRight: '5px' }}>Check-in To:</label>
            <input type="date" id="checkInTo" value={checkInDateToFilter} onChange={e => setCheckInDateToFilter(e.target.value)} />
          </div>
          <div>
            <label htmlFor="guestEmail" style={{ marginRight: '5px' }}>Guest Email:</label>
            <input type="text" id="guestEmail" placeholder="Search email..." value={guestEmailFilter} onChange={e => setGuestEmailFilter(e.target.value)} />
          </div>
          <button onClick={handleApplyFilters} style={{padding: '5px 10px'}}>Apply Filters</button>
          <button onClick={handleClearFilters} style={{padding: '5px 10px'}}>Clear Filters</button>
        </div>
      </div>

      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>Reservation List ({totalCount})</h3>
        <Link to="/app/reservations/new">
          <button style={{padding: '8px 15px'}}>Create New Reservation</button>
        </Link>
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
            {reservations.map(res => (
              <tr key={res.id}>
                <td>{res.id}</td>
                <td>{res.guest?.first_name} {res.guest?.last_name} ({res.guest?.email})</td>
                <td>{res.room?.room_number} ({res.room?.room_type})</td>
                <td>{res.check_in_date}</td>
                <td>{res.check_out_date}</td>
                <td>{res.status_display || res.status}</td>
                <td>
                  <Link to={`/app/reservations/${res.id}`} style={{ marginRight: '10px' }}>View</Link>
                  <Link to={`/app/reservations/${res.id}/edit`}>Edit</Link>
                  {/* Add other actions like Cancel, Check-in/out buttons here later */}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button onClick={handlePreviousPage} disabled={currentPage <= 1 || isLoading}>
          Previous
        </button>
        <span>Page {currentPage} of {totalPages} (Total: {totalCount} reservations)</span>
        <button onClick={handleNextPage} disabled={currentPage >= totalPages || isLoading}>
          Next
        </button>
      </div>
    </div>
  );
};

export default ReservationsListPage;
