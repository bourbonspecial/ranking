import { api } from './api.js'

export const session = $state({ me: undefined }) // undefined = loading, null = anonymous

export async function refreshMe() {
  try { session.me = await api.get('/api/me') } catch { session.me = null }
  return session.me
}
export async function logout() {
  await api.post('/api/auth/logout'); session.me = null
}
