import apiClient from './api.service';

const reservationService = {
  /**
   * Fetches a list of all reservations.
   * @param {object} params - Query parameters for filtering, sorting, pagination (e.g., { page: 1, status: 'CONFIRMED' })
   */
  getAllReservations: async (params) => {
    try {
      const response = await apiClient.get('/bookings/reservations/', { params });
      return response.data; // Expected: { count, next, previous, results: [...] }
    } catch (error) {
      console.error('Error fetching reservations:', error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Fetches details for a single reservation.
   * @param {string|number} id - The ID of the reservation.
   */
  getReservationById: async (id) => {
    try {
      const response = await apiClient.get(`/bookings/reservations/${id}/`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching reservation ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Creates a new reservation (or a group of reservations).
   * @param {object|array} reservationData - Data for the new reservation or an array for group booking.
   */
  createReservation: async (reservationData) => {
    try {
      // The backend ViewSet's create method handles both single and list data for group bookings.
      const response = await apiClient.post('/bookings/reservations/', reservationData);
      return response.data;
    } catch (error) {
      console.error('Error creating reservation:', error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Updates an existing reservation.
   * @param {string|number} id - The ID of the reservation to update.
   * @param {object} reservationData - Data to update.
   */
  updateReservation: async (id, reservationData) => {
    try {
      const response = await apiClient.patch(`/bookings/reservations/${id}/`, reservationData); // Using PATCH for partial updates
      return response.data;
    } catch (error) {
      console.error(`Error updating reservation ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Deletes a reservation.
   * Note: Backend might change status to CANCELLED instead of actual deletion.
   * @param {string|number} id - The ID of the reservation to delete.
   */
  deleteReservation: async (id) => {
    try {
      const response = await apiClient.delete(`/bookings/reservations/${id}/`);
      return response.data; // Or response.status if 204 No Content
    } catch (error) {
      console.error(`Error deleting reservation ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },

  // --- Custom Actions ---

  /**
   * Checks in a reservation.
   * @param {string|number} id - The ID of the reservation.
   */
  checkInReservation: async (id) => {
    try {
      const response = await apiClient.post(`/bookings/reservations/${id}/check_in/`);
      return response.data;
    } catch (error) {
      console.error(`Error checking in reservation ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Checks out a reservation.
   * @param {string|number} id - The ID of the reservation.
   */
  checkOutReservation: async (id) => {
    try {
      const response = await apiClient.post(`/bookings/reservations/${id}/check_out/`);
      return response.data;
    } catch (error) {
      console.error(`Error checking out reservation ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Cancels a reservation.
   * @param {string|number} id - The ID of the reservation.
   */
  cancelReservation: async (id) => {
    try {
      const response = await apiClient.post(`/bookings/reservations/${id}/cancel/`);
      return response.data;
    } catch (error) {
      console.error(`Error cancelling reservation ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Manages special requests for a reservation (e.g., early check-in, late check-out approval).
   * @param {string|number} id - The ID of the reservation.
   * @param {object} data - Data for special requests (e.g., { is_early_check_in_approved: true, early_check_in_fee: "20.00" }).
   */
  manageSpecialRequests: async (id, data) => {
    try {
      const response = await apiClient.patch(`/bookings/reservations/${id}/manage-special-requests/`, data);
      return response.data;
    } catch (error) {
      console.error(`Error managing special requests for reservation ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Changes the room for a reservation.
   * @param {string|number} id - The ID of the reservation.
   * @param {string|number} newRoomId - The ID of the new room.
   */
  changeRoom: async (id, newRoomId) => {
    try {
      const response = await apiClient.post(`/bookings/reservations/${id}/change_room/`, { new_room_id: newRoomId });
      return response.data;
    } catch (error) {
      console.error(`Error changing room for reservation ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },
};

export default reservationService;
