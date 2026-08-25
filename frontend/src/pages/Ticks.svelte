<script>
  import { api } from '../lib/api.js'
  import { session, refreshMe } from '../lib/session.svelte.js'
  let problems = $state([]), ticked = $state(new Set()), q = $state(''), saved = $state(false), err = $state(''), busy = $state(false)
  let dirty = $state(false)

  $effect(() => { load() })
  async function load() {
    const [ps, mine] = await Promise.all([api.get('/api/problems'), api.get('/api/me/ascents')])
    problems = ps; ticked = new Set(mine)
  }
  function toggle(id) {
    const n = new Set(ticked); n.has(id) ? n.delete(id) : n.add(id); ticked = n; dirty = true; saved = false
  }
  async function save() {
    busy = true; err = ''
    try { await api.put('/api/me/ascents', { problem_ids: [...ticked] }); saved = true; dirty = false; await refreshMe() }
    catch (x) { err = x.message } finally { busy = false }
  }
  let shown = $derived(problems.filter(p => !q || (p.name + ' ' + p.crag + ' ' + p.grade).toLowerCase().includes(q.toLowerCase())))
  let grades = $derived([...new Set(problems.map(p => p.grade))])
</script>

<div class="container">
  <div class="row" style="justify-content: space-between; margin-bottom: 1rem">
    <div>
      <h1>My ascents</h1>
      <p class="muted">Tick everything you've climbed. You'll only ever be asked about problems on this list.</p>
    </div>
    <div class="row">
      <span class="muted">{ticked.size} ticked</span>
      <button class="primary" onclick={save} disabled={busy || !dirty}>Save</button>
    </div>
  </div>
  <div class="status small" aria-live="polite">
    {#if err}<span class="error">{err}</span>
    {:else if saved}<span class="ok">Saved.</span> {#if ticked.size >= 2}<a href="/compare">Start comparing →</a>{:else}Tick at least two problems to start comparing.{/if}
    {:else if dirty}<span class="muted">Unsaved changes — un-ticking a problem removes any answers you've given about it.</span>
    {:else}<span class="faint">Your ascents are never shown to other members.</span>{/if}
  </div>

  <div class="field"><input placeholder="Search by name, crag or grade…" bind:value={q} /></div>

  {#each grades as g}
    {@const rows = shown.filter(p => p.grade === g)}
    {#if rows.length}
      <h3 style="margin-top: 1.25rem">{g}</h3>
      <div class="grid">
        {#each rows as p}
          <label class="tick" class:on={ticked.has(p.id)}>
            <input type="checkbox" checked={ticked.has(p.id)} onchange={() => toggle(p.id)} />
            <span><strong>{p.name}</strong><br/><span class="small muted">{p.crag}{p.fa_name ? ` · ${p.fa_name}` : ''}</span></span>
          </label>
        {/each}
      </div>
    {/if}
  {/each}
</div>

<style>
  .status { min-height: 1.5rem; margin-bottom: .75rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: .5rem; }
  .tick { display: flex; gap: .7rem; align-items: flex-start; padding: .6rem .75rem; border: 1px solid var(--line); border-radius: 8px; cursor: pointer; background: var(--bg2); color: var(--fg); font-size: .95rem; }
  .tick.on { border-color: var(--accent); }
  .tick input { width: auto; margin-top: .3rem; accent-color: var(--accent); }
</style>
