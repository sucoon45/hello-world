import React, { createContext, useState, useContext, useEffect } from 'react';
import authService from '../services/auth.service'; // For parseJwt, if needed here

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem('authToken'));
  const [user, setUser] = useState(() => {
    const storedUser = localStorage.getItem('authUser');
    try {
      return storedUser ? JSON.parse(storedUser) : null;
    } catch (error) {
      console.error("Error parsing stored user:", error);
      localStorage.removeItem('authUser'); // Clear corrupted data
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState(true); // To manage initial auth check

  useEffect(() => {
    // This effect runs once on mount to check initial auth state
    // If a token exists, you might want to validate it with the backend here
    // or parse it to ensure it's not expired and get user details.
    // For this iteration, we trust the stored token and user initially if present.
    // A more robust solution involves a /users/me endpoint call.

    const storedToken = localStorage.getItem('authToken');
    const storedUserJson = localStorage.getItem('authUser');

    if (storedToken && storedUserJson) {
      try {
        const storedUser = JSON.parse(storedUserJson);
        setToken(storedToken);
        setUser(storedUser);
        // TODO: Optionally verify token with backend here, e.g. by fetching user profile
        // If token is invalid/expired, call logout()
      } catch (error) {
        console.error("Error initializing auth state from localStorage:", error);
        // Clear potentially corrupted storage
        localStorage.removeItem('authToken');
        localStorage.removeItem('authUser');
        setToken(null);
        setUser(null);
      }
    }
    setIsLoading(false); // Finished initial auth check
  }, []);


  const login = (newToken, newUserDetails) => {
    localStorage.setItem('authToken', newToken);
    localStorage.setItem('authUser', JSON.stringify(newUserDetails)); // Store user details
    setToken(newToken);
    setUser(newUserDetails);
  };

  const logout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('authUser');
    setToken(null);
    setUser(null);
    // authService.logout(); // If authService.logout() handles backend token invalidation
  };

  const isAuthenticated = () => {
    // Could add token expiry check here if token is a JWT and parsable
    // For now, just checks if token exists.
    return !!token;
  };

  // Don't render children until initial auth check is complete
  if (isLoading) {
    return <div>Loading authentication...</div>; // Or a spinner component
  }

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  return useContext(AuthContext);
};
