<script>
  import { api } from '../lib/api.js'
  import { session, refreshMe } from '../lib/session.svelte.js'
  let progress = $state(null), err = $state(''), busy = $state(false), copied = $state(false)
  $effect(() => { load() })
  async function load() { progress = await api.get('/api/me/progress') }
  async function setPublic(v) {
    busy = true; err = ''
    try { await api.patch('/api/me', { public_profile: v }); await refreshMe() } catch (x) { err = x.message } finally { busy = false }
  }
  let url = $derived(`${location.origin}/climber/${session.me.id}`)
  async function copy() { try { await navigator.clipboard.writeText(url); copied = true; setTimeout(() => (copied = false), 1500) } catch {} }
</script>

<div class="container">
  <h1>{session.me.name} {#if session.me.is_test}<span class="pill test">test user</span>{/if}</h1>
  <p class="muted">{session.me.email} {#if session.me.is_admin}· admin{/if}</p>
  {#if session.me.is_test}<div class="notice small">You're set up as a <strong>test user</strong>: everything works as normal, but your comparisons are not counted in the global list. Your personal ordering still uses them.</div>{/if}
  {#if progress}
    <div class="row" style="margin: 1rem 0 2rem; gap:.75rem">
      <div class="card stat"><div class="big">{progress.n_done}</div><div class="muted small">climbed</div></div>
      <div class="card stat"><div class="big">{progress.n_tried}</div><div class="muted small">tried</div></div>
      <div class="card stat"><div class="big">{progress.n_done_answered + progress.n_attempt_answered}</div><div class="muted small">comparisons</div></div>
    </div>
  {/if}

  <div class="card" style="max-width: 640px">
    <h2>Visibility</h2>
    <p class="muted small">Your <a href="/ranking">personal ordering</a> and your answers are private by default. Making them public gives you a link anyone can open — no sign-in needed. The global list stays members-only either way.</p>
    <label class="row" style="gap:.6rem; cursor:pointer; margin: .5rem 0 0">
      <input type="checkbox" checked={session.me.public_profile} disabled={busy} onchange={(e) => setPublic(e.target.checked)} style="width:auto; accent-color: var(--accent)" />
      <span>Make my personal ordering and answers public</span>
    </label>
    {#if session.me.public_profile}
      <div class="row" style="margin-top: .9rem">
        <input readonly value={url} style="flex:1; min-width: 240px" onclick={(e) => e.target.select()} />
        <button onclick={copy}>{copied ? 'Copied' : 'Copy link'}</button>
        <a class="btn" href="/climber/{session.me.id}">Open →</a>
      </div>
    {/if}
    {#if err}<p class="error small" style="margin-top:.5rem">{err}</p>{/if}
  </div>
</div>
<style>.pill.test { border-color: var(--accent2); color: var(--accent2); vertical-align: middle; font-size: .7rem; }
.stat { min-width: 120px; } @media (max-width: 640px) { .stat { min-width: 0; flex: 1 1 28%; } } .big { font-size: 1.8rem; font-family: var(--mono); }</style>
