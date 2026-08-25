<script>
  import { api } from '../lib/api.js'
  let mode = $state('request') // request | signin
  let name = $state(''), email = $state(''), note = $state('')
  let done = $state(false), err = $state(''), busy = $state(false)

  async function submit(e) {
    e.preventDefault(); err = ''; busy = true
    try {
      if (mode === 'request') await api.post('/api/invite-requests', { name, email, note })
      else await api.post('/api/auth/request-link', { email })
      done = true
    } catch (x) { err = x.message } finally { busy = false }
  }
</script>

<div class="landing">
  <div class="inner">
    <div class="eyebrow">8C+ and above · by invitation</div>
    <h1>Some of them are harder than the grade says.<br/>You already know which.</h1>
    <p class="lede">
      A private ordering of the world's hardest boulder problems, built one question at a time
      by the people who have actually climbed them. No grades to argue over — just:
      <em>which was harder for you?</em>
    </p>
    <p class="lede muted">
      Membership requires at least two ascents at 8C+ or harder. Your answers are never shown to anyone.
      The list is only visible to those who contribute to it.
    </p>

    {#if done}
      <div class="card">
        {#if mode === 'request'}
          <h2>Noted.</h2>
          <p class="muted">If the ascents check out, an invitation will find its way to <span class="mono">{email}</span>.</p>
        {:else}
          <h2>Check your email.</h2>
          <p class="muted">If <span class="mono">{email}</span> belongs to a member, a sign-in link is on its way. It's valid for 30 minutes.</p>
        {/if}
      </div>
    {:else}
      <div class="card">
        <div class="tabs">
          <button class:sel={mode === 'request'} class="ghost" onclick={() => (mode = 'request')}>Request an invitation</button>
          <button class:sel={mode === 'signin'} class="ghost" onclick={() => (mode = 'signin')}>Already a member</button>
        </div>
        <form onsubmit={submit}>
          {#if mode === 'request'}
            <div class="field"><label for="n">Name</label><input id="n" bind:value={name} required maxlength="120" /></div>
          {/if}
          <div class="field"><label for="e">Email</label><input id="e" type="email" bind:value={email} required /></div>
          {#if mode === 'request'}
            <div class="field">
              <label for="t">What have you climbed at 8C+ or harder?</label>
              <textarea id="t" rows="3" bind:value={note} placeholder="Problem names are enough."></textarea>
            </div>
          {/if}
          {#if err}<p class="error small">{err}</p>{/if}
          <button class="primary" disabled={busy}>{mode === 'request' ? 'Request invitation' : 'Send me a sign-in link'}</button>
        </form>
      </div>
    {/if}
  </div>
</div>

<style>
  .landing { min-height: 100vh; display: grid; place-items: center; padding: 2rem 1.25rem; background:
    radial-gradient(ellipse at 20% 0%, #1a1608 0%, transparent 55%), var(--bg); }
  .inner { max-width: 620px; width: 100%; }
  .eyebrow { font-size: .75rem; letter-spacing: .18em; text-transform: uppercase; color: var(--accent); margin-bottom: 1.25rem; }
  h1 { font-size: clamp(1.6rem, 4vw, 2.4rem); line-height: 1.15; margin-bottom: 1.25rem; }
  .lede { font-size: 1.05rem; }
  .card { margin-top: 1.5rem; }
  .tabs { display: flex; gap: .25rem; margin-bottom: 1rem; border-bottom: 1px solid var(--line); }
  .tabs button { border: none; border-radius: 0; border-bottom: 2px solid transparent; color: var(--fg2); padding: .5rem .75rem; }
  .tabs button.sel { color: var(--fg); border-bottom-color: var(--accent); }
</style>
