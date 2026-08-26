<script>
  import { route } from './lib/router.svelte.js'
  import { session, refreshMe, logout } from './lib/session.svelte.js'
  import Landing from './pages/Landing.svelte'
  import Ticks from './pages/Ticks.svelte'
  import Compare from './pages/Compare.svelte'
  import MyComparisons from './pages/MyComparisons.svelte'
  import Ranking from './pages/Ranking.svelte'
  import Profile from './pages/Profile.svelte'
  import Admin from './pages/Admin.svelte'
  import PublicProfile from './pages/PublicProfile.svelte'
  import Footer from './lib/Footer.svelte'
  import Logo from './lib/Logo.svelte'

  refreshMe()
  let menuOpen = $state(false)
  $effect(() => { route.path; menuOpen = false })  // close on navigation

  const memberPages = { '/ticks': Ticks, '/compare': Compare, '/mine': MyComparisons, '/ranking': Ranking, '/profile': Profile }
  const links = [['/ranking', 'The list'], ['/compare', 'Compare'], ['/ticks', 'My ascents'], ['/mine', 'My answers'], ['/profile', 'Profile']]
  const isPublicProfile = (p) => /^\/climber\/\d+$/.test(p)

  let page = $derived.by(() => {
    if (session.me === undefined) return null
    if (isPublicProfile(route.path)) return PublicProfile
    if (!session.me) return Landing
    if (route.path === '/admin') return session.me.is_admin ? Admin : Ranking
    return memberPages[route.path] ?? (route.path === '/' ? (session.me.n_ascents ? Ranking : Ticks) : Ranking)
  })
</script>

{#if session.me}
  <nav class="top" class:open={menuOpen}>
    <a href="/" class="brand"><Logo size={22} /> The List</a>
    <button class="ghost burger" aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen} onclick={() => (menuOpen = !menuOpen)}>
      <span></span><span></span><span></span>
    </button>
    <div class="links">
      {#each links as [href, label]}
        <a {href} class:active={route.path === href}>{label}</a>
      {/each}
      {#if session.me.is_admin}<a href="/admin" class:active={route.path === '/admin'}>Admin</a>{/if}
      <button class="ghost small" onclick={logout}>Sign out</button>
    </div>
  </nav>
{/if}

{#if page}
  {@const Page = page}
  <Page />
  <Footer />
{/if}
