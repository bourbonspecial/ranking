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
    <div class="eyebrow">8C and above · by invitation</div>
    <h1>Some of them are harder than the grade says.<br/>You already know which.</h1>
    <p class="lede">
      A single ordering of the world's hardest boulder problems, built one question at a time
      by the people who have actually climbed them. No grades to argue over — just:
      <em>which was harder for you?</em>
    </p>

    <section class="how">
      <h2>How it works</h2>
      <ol>
        <li><strong>Tell us what you've climbed.</strong> Every problem 8C and harder is in the database. Tick yours — and, if you like, the ones you've tried but not done.</li>
        <li><strong>Answer one question at a time.</strong> We show you two problems from your own list and ask which was harder <em>for you</em>: A, B, or very similar. Keyboard-fast. Change your mind any time.</li>
        <li><strong>The list assembles itself.</strong> Every answer is a match between two problems. A Bradley–Terry model (a cousin of chess Elo) turns thousands of these matches into one ordered list, with a confidence measure for each problem. Grades only seed it; opinions overwrite them.</li>
        <li><strong>See where things really sit.</strong> A problem that most people rank above the 8C+s while it still gets 8C is probably due an upgrade. The list makes that visible without anyone having to say it.</li>
      </ol>
    </section>

    <section class="how">
      <h2>Who can see what</h2>
      <ul>
        <li>Membership requires at least two ascents at 8C or harder, and is by invitation.</li>
        <li>Your individual answers are never shown to other members.</li>
        <li>The global list is currently members-only. Once there are enough votes for it to mean something, it will be made public.</li>
        <li>Your own personal ordering and answers are private by default. You can choose to make them public from your profile.</li>
      </ul>
    </section>

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
              <label for="t">Name a couple of problems you have climbed which are generally considered 8C or harder</label>
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
  .landing { min-height: 100vh; display: grid; place-items: start center; padding: 3rem 1.25rem 4rem; background:
    radial-gradient(ellipse at 20% 0%, #1a1608 0%, transparent 55%), var(--bg); }
  .inner { max-width: 640px; width: 100%; }
  .eyebrow { font-size: .75rem; letter-spacing: .18em; text-transform: uppercase; color: var(--accent); margin-bottom: 1.25rem; }
  h1 { font-size: clamp(1.6rem, 4vw, 2.4rem); line-height: 1.15; margin-bottom: 1.25rem; }
  .lede { font-size: 1.05rem; }
  .how { margin-top: 2rem; }
  .how h2 { font-size: .8rem; letter-spacing: .12em; text-transform: uppercase; color: var(--fg2); margin-bottom: .75rem; }
  .how ol, .how ul { margin: 0; padding-left: 1.25rem; color: var(--fg2); }
  .how li { margin-bottom: .6rem; } .how li strong { color: var(--fg); }
  .card { margin-top: 2rem; }
  .tabs { display: flex; gap: .25rem; margin-bottom: 1rem; border-bottom: 1px solid var(--line); }
  .tabs button { border: none; border-radius: 0; border-bottom: 2px solid transparent; color: var(--fg2); padding: .5rem .75rem; }
  .tabs button.sel { color: var(--fg); border-bottom-color: var(--accent); }
</style>
