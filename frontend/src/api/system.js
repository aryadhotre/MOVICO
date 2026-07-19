import { apiFetch } from './client.js';

export async function getHealth() {
  return apiFetch('/api/system/health');
}

export async function getMetrics() {
  return apiFetch('/api/system/metrics');
}
