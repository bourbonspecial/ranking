// Minimal hash-free router using history API.
export const route = $state({ path: location.pathname })

export function navigate(path) {
  if (path === route.path) return
  history.pushState({}, '', path)
  route.path = path
}
window.addEventListener('popstate', () => { route.path = location.pathname })
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href]')
  if (!a || a.target === '_blank' || a.hasAttribute('data-external')) return
  const url = new URL(a.href)
  if (url.origin !== location.origin || url.pathname.startsWith('/api/')) return
  e.preventDefault(); navigate(url.pathname)
})
