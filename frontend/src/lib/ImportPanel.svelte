<script>
  // Import ascents from climbing-history.org: find your record, review what matches, apply.
  // Nothing is saved here - `onapply` hands the chosen statuses back to the ascents page,
  // which merges them into its list; the member then presses Save as usual.
  import { api } from './api.js'
  let { current = {}, onapply, onclose } = $props()
  let q = $state(''), climbers = $state(null), chosen = $state(null), preview = $state(null)
  let busy = $state(false), err = $state('')
  let include = $state({})   // problem id -> true when the row should be applied

  async function search(e) {
    e?.preventDefault(); if (q.trim().length < 2) return
    busy = true; err = ''; climbers = null; chosen = null; preview = null
    try { climbers = await api.get(`/api/me/sync/climbing-history/climbers?q=${encodeURIComponent(q.trim())}`) }
    catch (x) { err = x.message } finally { busy = false }
  }
  async function pick(c) {
    busy = true; err = ''; chosen = c; preview = null
    try {
      preview = await api.get(`/api/me/sync/climbing-history/climbers/${c.climber_id}/preview`)
      const inc = {}
      for (const m of preview.matched) inc[m.problem.id] = m.current !== m.status  // pre-tick what would change
      include = inc
    } catch (x) { err = x.message } finally { busy = false }
  }
  let changes = $derived(preview ? preview.matched.filter(m => include[m.problem.id]) : [])
  function apply() { onapply(changes.map(m => [m.problem.id, m.status])); onclose() }
  const label = (s) => s === 'done' ? 'climbed' : s === 'tried' ? 'tried' : 'not ticked'
</script>

<div class="card import">
  <div class="row" style="justify-content: space-between; align-items: baseline">
    <h3 style="margin: 0">Import from climbing-history.org</h3>
    <button type="button" class="ghost small" onclick={onclose}>Close</button>
  </div>
  <p class="muted small">Find yourself on climbing-history.org and we'll tick the boulders it has for you — sends as <strong>climbed</strong>, unfinished attempts as <strong>tried</strong>. You review the list before anything is applied, and nothing is ever written back to climbing-history.org.</p>

  <form onsubmit={search} class="row" style="gap: .5rem; margin-bottom: .75rem">
    <input placeholder="Your name as it appears on climbing-history.org" bind:value={q} minlength="2" style="flex: 1; min-width: 200px" />
    <button class="primary" disabled={busy || q.trim().length < 2}>Find me</button>
  </form>
  {#if err}<p class="error small">{err}</p>{/if}

  {#if climbers && !chosen}
    {#if !climbers.length}<p class="muted small">No climber with two or more ascents at 8C or harder matches “{q}”. Try a shorter part of your name.</p>
    {:else}
      <div class="list">
        {#each climbers as c}
          <button type="button" class="pickrow" onclick={() => pick(c)} disabled={busy}>
            <span><strong>{c.climber_name}</strong> <span class="muted small">· {c.hard_boulder_count} boulder{c.hard_boulder_count === 1 ? '' : 's'} at 8C or harder</span></span>
            <span class="small">That's me →</span>
          </button>
        {/each}
      </div>
    {/if}
  {/if}

  {#if chosen && preview}
    <p class="small muted" style="margin: .25rem 0 .75rem">Showing <strong>{chosen.climber_name}</strong> <a href={chosen.climber_url} target="_blank" rel="noopener">↗</a> · <button type="button" class="ghost small" onclick={() => { chosen = null; preview = null }}>not you?</button></p>
    {#if !preview.matched.length}
      <p class="muted small">None of their boulders are on the list yet.</p>
    {:else}
      <table class="small">
        <thead><tr><th></th><th>Problem</th><th>climbing-history says</th><th>You have</th></tr></thead>
        <tbody>
          {#each preview.matched as m}
            {@const same = m.current === m.status}
            <tr class:same>
              <td><input type="checkbox" bind:checked={include[m.problem.id]} disabled={same} style="width:auto" aria-label="Import {m.problem.name}" /></td>
              <td><strong>{m.problem.name}</strong> <span class="muted">{m.problem.grade} · {m.problem.crag}</span>{#if m.ch_name.toLowerCase() !== m.problem.name.toLowerCase()}<br/><span class="faint">listed there as “{m.ch_name}”</span>{/if}</td>
              <td>{label(m.status)}{#if m.date}&nbsp;<span class="faint">{m.date}</span>{/if}</td>
              <td class="muted">{same ? 'same' : label(m.current)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
    {#if preview.unmatched.length}
      <p class="small muted" style="margin-top: 1rem"><strong>Not on the list yet</strong> — {preview.unmatched.length} hard boulder{preview.unmatched.length === 1 ? '' : 's'} we couldn't match. Use “Add boulder” below to suggest one to the admins.</p>
      <ul class="small muted unmatched">
        {#each preview.unmatched as u}<li>{u.climb_name} <span class="faint">{u.grade}{u.crag_name ? ` · ${u.crag_name}` : ''} · {label(u.status)}</span> {#if u.climb_url}<a href={u.climb_url} target="_blank" rel="noopener">↗</a>{/if}</li>{/each}
      </ul>
    {/if}
    <div class="row" style="margin-top: 1rem; gap: .75rem; align-items: center">
      <button type="button" class="primary" onclick={apply} disabled={!changes.length}>Apply {changes.length} change{changes.length === 1 ? '' : 's'}</button>
      <span class="faint small">Saved to your list straight away.{#if preview.n_skipped}&nbsp;{preview.n_skipped} easier problem{preview.n_skipped === 1 ? '' : 's'} ignored.{/if}</span>
    </div>
  {/if}
</div>

<style>
  .import { margin-bottom: 1.25rem; }
  .list { display: flex; flex-direction: column; gap: .4rem; }
  .pickrow { display: flex; justify-content: space-between; align-items: center; text-align: left; width: 100%; padding: .6rem .8rem; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: .4rem .5rem; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: var(--fg3); font-weight: 500; }
  tr.same td { color: var(--fg3); }
  .unmatched { margin: .25rem 0 0 1rem; }
</style>
