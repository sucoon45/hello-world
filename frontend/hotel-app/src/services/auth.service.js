import apiClient from './api.service';

const login = async (credentials) => {
  try {
    const response = await apiClient.post('/token/', credentials); // Django Simple JWT default token endpoint
    if (response.data.access) {
      // Store tokens (e.g., in localStorage)
      localStorage.setItem('authToken', response.data.access);
      if (response.data.refresh) {
        localStorage.setItem('refreshToken', response.data.refresh);
      }
      // TODO: Decode token to get user info (username, role) or fetch user profile
      // For now, we'll just return the access token and let AuthContext handle user state.
      // A better approach would be to fetch user details here after successful login.
      // For example:
      // const userProfileResponse = await apiClient.get('/users/me/'); // Assuming a /me endpoint
      // return { token: response.data.access, user: userProfileResponse.data };

      // Placeholder user object - replace with actual user data from token or API call
      const decodedToken = parseJwt(response.data.access); // Implement parseJwt or use a library
      const user = {
        username: decodedToken?.username || 'User', // Adjust based on your JWT payload
        role: decodedToken?.role || 'GUEST', // Adjust based on your JWT payload
        // Add other user details from token if available
      };

      return { token: response.data.access, user };
    } else {
      throw new Error('Login failed: No access token received.');
    }
  } catch (error) {
    console.error('Login error:', error.response ? error.response.data : error.message);
    // Re-throw a more specific error or handle it
    throw error.response ? new Error(error.response.data.detail || 'Login failed') : error;
  }
};

const logout = () => {
  // Remove tokens from storage
  localStorage.removeItem('authToken');
  localStorage.removeItem('refreshToken');
  // TODO: Optionally, call a backend endpoint to blacklist the refresh token if using Simple JWT blacklist feature
  // try {
  //   await apiClient.post('/token/blacklist/', { refresh: localStorage.getItem('refreshToken') });
  // } catch (error) {
  //   console.error('Error blacklisting token:', error);
  // }
};

// Helper function to parse JWT (basic implementation, consider a library for robustness)
// This is a simplified parser and does not verify the token signature.
// For actual user data from token, backend should provide a /users/me/ endpoint
// or include necessary user info (like role) in the JWT claims.
const parseJwt = (token) => {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
};


// TODO: Implement refreshToken function if using refresh tokens
// const refreshToken = async () => { ... }

const authService = {
  login,
  logout,
  // refreshToken, // if implemented
  parseJwt, // Exporting for potential use in AuthContext to initialize state
};

export default authService;
