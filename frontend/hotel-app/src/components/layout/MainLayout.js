import React from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const MainLayout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div>
      <nav style={{ backgroundColor: '#f0f0f0', padding: '10px', marginBottom: '20px' }}>
        <Link to="/app/dashboard" style={{ marginRight: '15px' }}>Dashboard</Link>
        <Link to="/app/reservations" style={{ marginRight: '15px' }}>Reservations</Link>
        {/* Add more links as needed, e.g., Rooms, Guests, Billing */}
        <span style={{ float: 'right' }}>
          {user ? (
            <>
              Logged in as: {user.username} ({user.role})
              <button onClick={handleLogout} style={{ marginLeft: '15px' }}>Logout</button>
            </>
          ) : (
            <Link to="/login">Login</Link>
          )}
        </span>
      </nav>
      <main style={{ padding: '20px' }}>
        <Outlet /> {/* Child routes will render here */}
      </main>
      <footer style={{ marginTop: '20px', padding: '10px', backgroundColor: '#f0f0f0', textAlign: 'center' }}>
        <p>&copy; {new Date().getFullYear()} Hotel Management System</p>
      </footer>
    </div>
  );
};

export default MainLayout;
