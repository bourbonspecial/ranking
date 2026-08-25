<script>
  import { api } from '../lib/api.js'
  import { refreshMe } from '../lib/session.svelte.js'
  let problems = $state([]), status = $state({}), q = $state(''), saved = $state(false), err = $state(''), busy = $state(false)
  let dirty = $state(false)

  $effect(() => { load() })
  async function load() {
    const [ps, mine] = await Promise.all([api.get('/api/problems'), api.get('/api/me/ascents')])
    problems = ps
    const st = {}; mine.done.forEach(id => (st[id] = 'done')); mine.tried.forEach(id => (st[id] = 'tried'))
    status = st
  }
  function set(id, value) {
    const st = { ...status }
    if (st[id] === value) delete st[id]; else st[id] = value
    status = st; dirty = true; saved = false
  }
  async function save() {
    busy = true; err = ''
    const done = Object.keys(status).filter(k => status[k] === 'done').map(Number)
    const tried = Object.keys(status).filter(k => status[k] === 'tried').map(Number)
    try { await api.put('/api/me/ascents', { done, tried }); saved = true; dirty = false; await refreshMe() }
    catch (x) { err = x.message } finally { busy = false }
  }
  let nDone = $derived(Object.values(status).filter(v => v === 'done').length)
  let nTried = $derived(Object.values(status).filter(v => v === 'tried').length)
  let shown = $derived(problems.filter(p => !q || (p.name + ' ' + p.crag + ' ' + p.grade).toLowerCase().includes(q.toLowerCase())))
  let grades = $derived([...new Set(problems.map(p => p.grade))])
</script>

<div class="container">
  <div class="row" style="justify-content: space-between; margin-bottom: 1rem">
    <div>
      <h1>My ascents</h1>
      <p class="muted">Mark everything you've <strong>climbed</strong>, and optionally what you've <strong>tried</strong> but not done. You'll only be asked about problems on this list.</p>
    </div>
    <div class="row">
      <span class="muted">{nDone} climbed · {nTried} tried</span>
      <button class="primary" onclick={save} disabled={busy || !dirty}>Save</button>
    </div>
  </div>
  <div class="status small" aria-live="polite">
    {#if err}<span class="error">{err}</span>
    {:else if saved}<span class="ok">Saved.</span> {#if nDone >= 2}<a href="/compare">Start comparing →</a>{:else}Mark at least two problems as climbed to start comparing.{/if}
    {:else if dirty}<span class="muted">Unsaved changes — removing a problem removes any answers you've given about it.</span>
    {:else}<span class="faint">Your list is never shown to other members. Comparisons involving problems you've only tried count for less.</span>{/if}
  </div>

  <div class="field"><input placeholder="Search by name, crag or grade…" bind:value={q} /></div>

  {#each grades as g}
    {@const rows = shown.filter(p => p.grade === g)}
    {#if rows.length}
      <h3 style="margin-top: 1.25rem">{g}</h3>
      <div class="grid">
        {#each rows as p}
          <div class="tick" class:done={status[p.id] === 'done'} class:tried={status[p.id] === 'tried'}>
            <span class="info"><strong>{p.name}</strong><br/><span class="small muted">{p.crag}{p.fa_name ? ` · ${p.fa_name}` : ''}</span></span>
            <span class="seg">
              <button class:on={status[p.id] === 'done'} onclick={() => set(p.id, 'done')} title="I've climbed this">Done</button>
              <button class:on={status[p.id] === 'tried'} onclick={() => set(p.id, 'tried')} title="I've tried this but not done it">Tried</button>
            </span>
          </div>
        {/each}
      </div>
    {/if}
  {/each}
</div>

<style>
  .status { min-height: 1.5rem; margin-bottom: .75rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: .5rem; }
  .tick { display: flex; gap: .7rem; align-items: center; justify-content: space-between; padding: .6rem .75rem; border: 1px solid var(--line); border-radius: 8px; background: var(--bg2); font-size: .95rem; }
  .tick.done { border-color: var(--accent); } .tick.tried { border-color: var(--fg3); }
  .info { min-width: 0; }
  .seg { display: inline-flex; flex-shrink: 0; }
  .seg button { padding: .25rem .6rem; font-size: .8rem; border-radius: 0; }
  .seg button:first-child { border-radius: 6px 0 0 6px; } .seg button:last-child { border-radius: 0 6px 6px 0; border-left: none; }
  .seg button.on { background: var(--accent); color: #111; border-color: var(--accent); }
  .tick.tried .seg button.on { background: var(--fg2); border-color: var(--fg2); }
</style>
