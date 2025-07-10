import apiClient from './api.service';

const roomService = {
  /**
   * Fetches a list of all rooms.
   * @param {object} params - Query parameters for filtering, sorting, pagination
   *                          (e.g., { page: 1, status: 'AVAILABLE', room_type__id: 1 })
   */
  getAllRooms: async (params) => {
    try {
      // Endpoint is /hotel/rooms/ as RoomViewSet is in hotel_core/views.py
      const response = await apiClient.get('/hotel/rooms/', { params });
      return response.data; // Expected: { count, next, previous, results: [...] }
    } catch (error) {
      console.error('Error fetching rooms:', error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Fetches details for a single room.
   * @param {string|number} id - The ID of the room.
   */
  getRoomById: async (id) => {
    try {
      const response = await apiClient.get(`/hotel/rooms/${id}/`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching room ${id}:`, error.response?.data || error.message);
      throw error;
    }
  },

  /**
   * Fetches all room types.
   */
  getAllRoomTypes: async (params) => {
    try {
      const response = await apiClient.get('/hotel/roomtypes/', { params });
      return response.data;
    } catch (error) {
      console.error('Error fetching room types:', error.response?.data || error.message);
      throw error;
    }
  }

  // Add createRoom, updateRoom, deleteRoom if admin functionality is built for these
};

export default roomService;
