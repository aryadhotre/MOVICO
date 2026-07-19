import React, { createContext, useContext, useState, useCallback } from 'react';
import { submitRating } from '../api/ratings';

/**
 * RatingContext provides:
 *   ratingVersion  – bumped after every successful rating submission
 *   submitRating   – wraps the API call; bumps version and fires onSuccess
 *   error / clearError – inline error string (no toast library)
 *
 * Any component that needs to re-fetch history or recommendations should
 * include ratingVersion in its useEffect dependency array.
 */
const RatingContext = createContext(null);

export function RatingProvider({ children }) {
  const [ratingVersion, setRatingVersion] = useState(0);
  const [error, setError] = useState('');

  const rate = useCallback(async (movieId, rating) => {
    setError('');
    try {
      const result = await submitRating(movieId, rating);
      setRatingVersion((v) => v + 1); // triggers re-fetch in dependants
      return result;
    } catch (err) {
      const msg = err?.message || 'Rating failed. Please try again.';
      setError(msg);
      throw err;
    }
  }, []);

  const clearError = useCallback(() => setError(''), []);

  return (
    <RatingContext.Provider value={{ ratingVersion, rate, error, clearError }}>
      {children}
    </RatingContext.Provider>
  );
}

/** Use inside any component that submits or reacts to ratings. */
export function useRating() {
  const ctx = useContext(RatingContext);
  if (!ctx) throw new Error('useRating must be used inside <RatingProvider>');
  return ctx;
}
