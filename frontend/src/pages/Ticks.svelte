<script>
  import { api } from '../lib/api.js'
  import { session } from '../lib/session.svelte.js'
  import DetailsForm from '../lib/DetailsForm.svelte'
  let detailsDismissed = $state(false)
  import ImportPanel from '../lib/ImportPanel.svelte'
  let importing = $state(false), importDismissed = $state(false)
  let canImport = $derived(!!session.me?.sync_sources?.includes('climbing_history'))
  function applyImport(changes) {
    const st = { ...status }
    for (const [id, value] of changes) st[id] = value
    status = st; dirty = changes.length > 0 || dirty; saved = false
  }
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
  let noMatch = $derived(!!q.trim() && shown.length === 0)

  // Reporting a boulder that isn't on the list yet: admins get an email and decide.
  let form = $state(null), sugBusy = $state(false), sugErr = $state(''), sugSent = $state('')
  function openForm() {
    sugErr = ''; sugSent = ''
    form = { name: q.trim(), crag: '', country: '', grade: grades[0] || '8C', fa_name: '', fa_date: '', note: '' }
  }
  async function suggest(e) {
    e.preventDefault()
    sugBusy = true; sugErr = ''
    try {
      await api.post('/api/problem-suggestions', form)
      sugSent = form.name; form = null; q = ''  // clear the search so the "no match" card doesn't come straight back
    } catch (x) { sugErr = x.message } finally { sugBusy = false }
  }
</script>

<div class="container">
  {#if session.me && !session.me.details_complete && !detailsDismissed}
    <div class="notice" style="margin-bottom: 1.5rem">
      <div class="row" style="justify-content: space-between; align-items: baseline">
        <strong>One quick thing first</strong>
        <button class="ghost small faint" onclick={() => (detailsDismissed = true)}>later</button>
      </div>
      <p class="muted small" style="margin: .25rem 0 .75rem">Your gender, height and arm span help us build filtered versions of the list down the line. Optional, private, and you can change it any time from your <a href="/profile">profile</a>.</p>
      <DetailsForm compact onsaved={() => (detailsDismissed = true)} />
    </div>
  {/if}
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

  {#if canImport && importing}
    <ImportPanel current={status} onapply={applyImport} onclose={() => (importing = false)} />
  {:else if canImport && !importDismissed}
    <div class="notice" style="margin-bottom: 1.5rem">
      <div class="row" style="justify-content: space-between; align-items: baseline">
        <strong>Save yourself some ticking</strong>
        <button class="ghost small faint" onclick={() => (importDismissed = true)}>later</button>
      </div>
      <p class="muted small" style="margin: .25rem 0 .75rem">If you log ascents on climbing-history.org we can pull them in for you: sends become <strong>climbed</strong>, unfinished attempts <strong>tried</strong>. You review everything before it's saved, and nothing is written back.</p>
      <button class="primary" onclick={() => (importing = true)}>Import from climbing-history.org</button>
    </div>
  {/if}

  <div class="field"><input placeholder="Search by name, crag or grade…" bind:value={q} /></div>

  {#if sugSent}
    <p class="ok small">Thanks — <strong>{sugSent}</strong> has been sent to the admins. They'll add it if it belongs on the list.</p>
  {/if}

  {#if noMatch && !form && problems.length}
    <div class="card empty">
      <p class="muted" style="margin:0">No problem matches “{q}”.</p>
      <button class="primary" onclick={openForm}>Add boulder</button>
    </div>
  {/if}

  {#if form}
    <div class="card">
      <h3 style="margin-top:0">Add a missing boulder</h3>
      <p class="muted small">This doesn't add it to the list straight away — it's sent to the admins to check first.</p>
      <form onsubmit={suggest}>
        <div class="formGrid">
          <div class="field"><label for="s-name">Name</label><input id="s-name" bind:value={form.name} required maxlength="120" /></div>
          <div class="field"><label for="s-grade">Grade</label>
            <select id="s-grade" bind:value={form.grade}>{#each grades as g}<option>{g}</option>{/each}</select>
          </div>
          <div class="field"><label for="s-crag">Crag</label><input id="s-crag" bind:value={form.crag} maxlength="120" /></div>
          <div class="field"><label for="s-country">Country</label><input id="s-country" bind:value={form.country} maxlength="120" /></div>
          <div class="field"><label for="s-fa">First ascent by</label><input id="s-fa" bind:value={form.fa_name} maxlength="120" /></div>
          <div class="field"><label for="s-date">First ascent date</label><input id="s-date" bind:value={form.fa_date} placeholder="2024-03" maxlength="40" /></div>
        </div>
        <div class="field"><label for="s-note">Anything else</label><textarea id="s-note" rows="2" bind:value={form.note} maxlength="2000"></textarea></div>
        {#if sugErr}<p class="error small">{sugErr}</p>{/if}
        <div class="row">
          <button class="primary" disabled={sugBusy}>Send to admins</button>
          <button type="button" class="ghost" onclick={() => (form = null)}>Cancel</button>
        </div>
      </form>
    </div>
  {/if}

  {#each grades as g}
    {@const rows = shown.filter(p => p.grade === g).sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))}
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
  .empty { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem 1.25rem; }
  .formGrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0 1rem; }
</style>
