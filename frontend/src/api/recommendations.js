import { apiFetch } from './client.js';

export async function getRecommendations({ limit = 10, bypassCache = false, includeExplanations = true } = {}) {
  const params = new URLSearchParams({
    limit,
    bypass_cache: bypassCache,
    include_explanations: includeExplanations
  }).toString();
  return apiFetch(`/api/recommendations?${params}`);
}
