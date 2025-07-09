import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ProtectedRoute = ({ allowedRoles }) => {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  // If allowedRoles is provided, check if the user's role is in the list
  // This assumes user object has a 'role' property matching backend roles (e.g., ADMIN, FRONT_DESK)
  if (allowedRoles && user && user.role && !allowedRoles.includes(user.role)) {
    // User is authenticated but does not have the required role
    // Redirect to a 'Forbidden' page or back to a safe page like dashboard
    // For now, let's redirect to dashboard, or show a simple forbidden message.
    // In a real app, you might redirect to an "Unauthorized" page.
    console.warn(`User role ${user.role} not in allowed roles: ${allowedRoles.join(', ')}`);
    return <Navigate to="/app/dashboard" replace />; // Or a specific /unauthorized page
  }

  return <Outlet />; // Render the child route component
};

export default ProtectedRoute;
