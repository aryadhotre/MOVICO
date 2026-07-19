import React from 'react';
import { Navigate } from 'react-router-dom';

/**
 * Wraps protected routes. If no JWT is found in localStorage,
 * redirects immediately to /login. No API call needed — the
 * individual pages handle 401 gracefully on their own.
 */
export default function ProtectedRoute({ children }) {
  const token = localStorage.getItem('jwt');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
