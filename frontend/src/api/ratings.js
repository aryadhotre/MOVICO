import { apiFetch } from './client.js';

export async function submitRating(movieId, rating) {
  return apiFetch('/api/ratings', {
    method: 'POST',
    body: JSON.stringify({ movie_id: movieId, rating }),
  });
}

export async function getHistory(page = 1, pageSize = 20) {
  return apiFetch(`/api/ratings/history?page=${page}&page_size=${pageSize}`);
}

export async function addToWatchlist(movieId) {
  return apiFetch('/api/ratings/watchlist', {
    method: 'POST',
    body: JSON.stringify({ movie_id: movieId }),
  });
}

export async function getWatchlist(page = 1, pageSize = 20) {
  return apiFetch(`/api/ratings/watchlist?page=${page}&page_size=${pageSize}`);
}

export async function removeFromWatchlist(id) {
  return apiFetch(`/api/ratings/watchlist/${id}`, {
    method: 'DELETE',
  });
}
