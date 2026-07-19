import { apiFetch } from './client.js';

export async function register(username, email, password) {
  return apiFetch('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
  });
}

export async function login(username, password) {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const data = await apiFetch('/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData.toString(),
  });

  if (data.access_token) {
    localStorage.setItem('jwt', data.access_token);
  }
  return data;
}

export async function getMe() {
  return apiFetch('/api/auth/me');
}
