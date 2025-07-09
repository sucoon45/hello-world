import axios from 'axios';

// Determine the base URL for the API.
// In development, this typically points to your local Django backend.
// In production, it would point to your deployed backend URL.
// Using REACT_APP_API_URL environment variable is a good practice.
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1/';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: To add the JWT token to requests
apiClient.interceptors.request.use(
  (config) => {
    // Retrieve token from where it's stored (e.g., localStorage, or AuthContext)
    // For now, assuming localStorage. This should align with AuthContext's storage.
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response Interceptor: To handle global errors like 401 (Unauthorized)
apiClient.interceptors.response.use(
  (response) => {
    // Any status code that lie within the range of 2xx cause this function to trigger
    return response;
  },
  (error) => {
    // Any status codes that falls outside the range of 2xx cause this function to trigger
    if (error.response) {
      const { status } = error.response;
      if (status === 401) {
        // Handle 401 Unauthorized: e.g., token expired or invalid
        // TODO: Implement token refresh logic or redirect to login
        console.error("API Error: 401 Unauthorized. Token may be invalid or expired.");
        // Potentially clear auth token and redirect to login
        localStorage.removeItem('authToken'); // Align with AuthContext
        // window.location.href = '/login'; // Hard redirect, or use React Router's navigate
      }
      // Handle other common errors globally if needed
      // else if (status === 403) { console.error("API Error: 403 Forbidden."); }
      // else if (status === 500) { console.error("API Error: 500 Internal Server Error."); }
    } else if (error.request) {
      // The request was made but no response was received
      console.error('API Error: No response received from server.', error.request);
    } else {
      // Something happened in setting up the request that triggered an Error
      console.error('API Error: Error setting up request.', error.message);
    }
    return Promise.reject(error);
  }
);

export default apiClient;
