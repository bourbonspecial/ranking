async function req(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'same-origin',
  })
  if (r.status === 204) return null
  let data = null
  try { data = await r.json() } catch { /* empty */ }
  if (!r.ok) {
    const msg = data?.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : r.statusText
    const e = new Error(msg); e.status = r.status; throw e
  }
  return data
}
export const api = {
  get: (p) => req('GET', p),
  post: (p, b) => req('POST', p, b ?? {}),
  put: (p, b) => req('PUT', p, b),
  patch: (p, b) => req('PATCH', p, b),
}
