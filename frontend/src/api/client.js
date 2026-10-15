/**
 * api/client.js
 * ─────────────
 * Centralised Axios instance and typed API helpers.
 * All components import from here — never raw fetch.
 *
 * The Vite dev-server proxy forwards /api → http://localhost:8000/api,
 * so BASE_URL works both in dev (via proxy) and production (same origin).
 */
import axios from 'axios'

const BASE_URL = '/api/v1'

const http = axios.create({
  baseURL: BASE_URL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Trash Bins ────────────────────────────────────────────────────────
export const binsApi = {
  list:        ()     => http.get('/bins/').then(r => r.data),
  overflowing: (pct)  => http.get('/bins/overflowing', { params: { threshold: pct } }).then(r => r.data),
  update:      (id, data) => http.patch(`/bins/${id}`, data).then(r => r.data),
}

// ── Trucks ────────────────────────────────────────────────────────────
export const trucksApi = {
  list:   () => http.get('/trucks/').then(r => r.data),
  update: (id, data) => http.patch(`/trucks/${id}`, data).then(r => r.data),
}

// ── Route Tasks ───────────────────────────────────────────────────────
export const tasksApi = {
  list:           (params) => http.get('/tasks/', { params }).then(r => r.data),
  updateStatus:   (id, status) => http.patch(`/tasks/${id}/status`, { status }).then(r => r.data),
}

// ── Crisis Events ─────────────────────────────────────────────────────
export const crisesApi = {
  list:    (params) => http.get('/crises/', { params }).then(r => r.data),
  report:  (data)   => http.post('/crises/', data).then(r => r.data),
  resolve: (id)     => http.patch(`/crises/${id}/resolve`).then(r => r.data),
}

// ── AI Agents ─────────────────────────────────────────────────────────
export const agentsApi = {
  runRouting:   ()  => http.post('/agents/routing/run').then(r => r.data),
  runCrisis:    (id)=> http.post(`/agents/crisis/run/${id}`).then(r => r.data),
  status:       ()  => http.get('/agents/status').then(r => r.data),
}
