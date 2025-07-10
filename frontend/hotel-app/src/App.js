import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import './App.css';

import MainLayout from './components/layout/MainLayout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ReservationsListPage from './pages/ReservationsListPage';
import ReservationDetailPage from './pages/ReservationDetailPage'; // Import new page
import ReservationFormPage from './pages/ReservationFormPage';   // Import new page
import NotFoundPage from './pages/NotFoundPage';
import ProtectedRoute from './routes/ProtectedRoute';
// import { useAuth } from './contexts/AuthContext'; // Currently not needed directly in App.js for this setup

function App() {
  // const { isAuthenticated } = useAuth(); // Can be used for initial redirect logic if needed here

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Protected Application Routes */}
      <Route
        path="/app"
        element={
          <ProtectedRoute> {/* Protects all routes under /app */}
            <MainLayout />
          </ProtectedRoute>
        }
      >
        {/* Default child route for /app, e.g., redirect to dashboard or make dashboard the index */}
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="reservations" element={<ReservationsListPage />} />
         <Route path="reservations/new" element={<ReservationFormPage />} />
         <Route path="reservations/:id" element={<ReservationDetailPage />} />
         <Route path="reservations/:id/edit" element={<ReservationFormPage />} />
        {/* Add more protected routes here as children of MainLayout */}
      </Route>

      {/* Redirect root to login or app dashboard based on auth state */}
      <Route
        path="/"
        element={
          // Simple redirect logic: if authenticated go to /app/dashboard, else to /login
          // This could also be handled by ProtectedRoute if / was a protected path itself.
          // For now, an explicit redirect. Consider where initial auth check happens.
          // If useAuth().isAuthenticated() is checked here, ensure AuthProvider is high enough.
          // For simplicity, let's assume a user visiting "/" without being logged in should see login.
          // If they are logged in, they'd typically already be at /app/dashboard.
          // This can be refined. For now, default to /login or /app/dashboard if already authed.
          // This specific redirect might be better handled by a component that checks auth.
          // For now, let's make "/" redirect to "/app/dashboard" and ProtectedRoute handles /login redirect.
          <Navigate to="/app/dashboard" replace />
        }
      />

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export default App;
