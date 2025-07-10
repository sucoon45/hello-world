import apiClient from './api.service';

const guestService = {
  /**
   * Fetches a list of all guests.
   * @param {object} params - Query parameters for filtering, sorting, pagination
   *                          (e.g., { page: 1, search: 'Doe' })
   */
  getAllGuests: async (params) => {
    try {
      // Assuming the backend endpoint for guests is under /bookings/guests/
      // as GuestViewSet is in reservations/views.py
      const response = await apiClient.get('/bookings/guests/', { params });
      return response.data; // Expected: { count, next, previous, results: [...] }
    } catch (error) {
      console.error('Error fetching guests:', error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Fetches details for a single guest.
   * @param {string|number} id - The ID of the guest.
   */
  getGuestById: async (id) => {
    try {
      const response = await apiClient.get(`/bookings/guests/${id}/`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching guest ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Creates a new guest.
   * @param {object} guestData - Data for the new guest.
   */
  createGuest: async (guestData) => {
    try {
      const response = await apiClient.post('/bookings/guests/', guestData);
      return response.data;
    } catch (error) {
      console.error('Error creating guest:', error.response?.data || error.message);
      throw error;
    }
  },

  // Add updateGuest, deleteGuest if needed later
};

export default guestService;
