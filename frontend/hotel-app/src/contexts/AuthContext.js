import React, { createContext, useState, useContext } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  // For now, store token and user in simple state.
  // In a real app, this would interact with localStorage/sessionStorage
  // and potentially make an API call to verify token/fetch user on load.
  const [token, setToken] = useState(null); // Store JWT token
  const [user, setUser] = useState(null);   // Store user object { username, role, etc. }

  const login = (newToken, newUser) => {
    setToken(newToken);
    setUser(newUser);
    // TODO: Persist token (e.g., localStorage.setItem('authToken', newToken);)
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    // TODO: Remove token from storage (e.g., localStorage.removeItem('authToken');)
  };

  const isAuthenticated = () => {
    return !!token; // Simple check, real app might verify token expiry
  };

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  return useContext(AuthContext);
};
