import { apiFetch } from './client.js';

export async function getGenres() {
  return apiFetch('/api/movies/genres');
}

export async function getTrending(page = 1, pageSize = 20) {
  return apiFetch(`/api/movies/trending?page=${page}&page_size=${pageSize}`);
}

export async function browse(params = {}) {
  const query = new URLSearchParams(params).toString();
  return apiFetch(`/api/movies/browse${query ? `?${query}` : ''}`);
}

export async function search(query, params = {}) {
  const q = new URLSearchParams({ q: query, ...params }).toString();
  return apiFetch(`/api/movies/search?${q}`);
}

export async function getMovieById(id) {
  return apiFetch(`/api/movies/${id}`);
}

export async function getSimilarMovies(id) {
  return apiFetch(`/api/movies/${id}/similar`);
}
