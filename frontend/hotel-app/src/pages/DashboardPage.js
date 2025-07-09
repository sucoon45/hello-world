import React from 'react';
import { useAuth } from '../contexts/AuthContext';

const DashboardPage = () => {
  const { user } = useAuth();

  return (
    <div>
      <h1>Dashboard</h1>
      {user ? (
        <p>Welcome, {user.username || 'User'}! Your role is: {user.role || 'N/A'}.</p>
      ) : (
        <p>Welcome to the hotel management dashboard.</p>
      )}
      <p>This is where key metrics and quick actions will be displayed.</p>
      {/* Placeholder for future dashboard widgets */}
    </div>
  );
};

export default DashboardPage;
