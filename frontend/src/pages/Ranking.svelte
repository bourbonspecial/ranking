<script>
  import { api } from '../lib/api.js'
  import { session } from '../lib/session.svelte.js'
  import PersonalTable from '../lib/PersonalTable.svelte'
  let tab = $state('global') // global | personal
  let data = $state(null), err = $state(''), locked = $state(null), algo = $state('bradley_terry'), q = $state(''), gradeFilter = $state('')
  let includeAttempts = $state(false)
  let mine = $state(null), progress = $state(null)
  const algos = [['bradley_terry', 'Bradley–Terry'], ['elo', 'Elo'], ['win_rate', 'Win rate']]

  $effect(() => { load(algo, includeAttempts) })
  $effect(() => { loadPersonal() })
  async function load(a, inc) {
    err = ''; locked = null
    try { data = await api.get(`/api/ranking?algo=${a}&include_attempts=${inc}`) }
    catch (x) { if (x.status === 403) locked = x.message; else err = x.message; data = null }
  }
  async function loadPersonal() {
    try { [mine, progress] = await Promise.all([api.get('/api/me/ranking'), api.get('/api/me/progress')]) } catch (x) { err = x.message }
  }
  let rows = $derived((data?.rows ?? []).filter(r =>
    (!gradeFilter || r.problem.grade === gradeFilter) &&
    (!q || (r.problem.name + ' ' + r.problem.crag).toLowerCase().includes(q.toLowerCase()))))
  let grades = $derived([...new Set((data?.rows ?? []).map(r => r.problem.grade))])
  const pct = (a, b) => b ? Math.round(100 * a / b) : 0
</script>

<div class="container">
  <div class="row" style="justify-content: space-between; margin-bottom: 1rem">
    <h1>The list</h1>
    <div class="tabs">
      <button class:sel={tab === 'global'} onclick={() => (tab = 'global')}>Global</button>
      <button class:sel={tab === 'personal'} onclick={() => (tab = 'personal')}>Personal</button>
    </div>
  </div>

  {#if tab === 'global'}
    {#if locked}
      <div class="card"><h2>Not yet.</h2><p class="muted">{locked}</p><a href="/compare" class="btn">Compare →</a></div>
    {:else if err}<p class="error">{err}</p>
    {:else if data}
      <div class="row stats">
        <div class="card stat"><div class="big">{data.stats.n_problems}</div><div class="muted small">problems</div></div>
        <div class="card stat"><div class="big">{data.stats.n_with_data} <span class="faint" style="font-size:1rem">· {pct(data.stats.n_with_data, data.stats.n_problems)}%</span></div><div class="muted small">voted on</div></div>
        <div class="card stat"><div class="big">{data.n_comparisons}</div><div class="muted small">comparisons</div></div>
        <div class="card stat"><div class="big">{data.stats.n_voters} <span class="faint" style="font-size:1rem">/ {data.stats.n_members}</span></div><div class="muted small">voters</div></div>
      </div>
      <div class="row" style="justify-content: space-between; margin: 1rem 0 .75rem">
        <p class="muted small" style="margin:0">{data.include_attempts ? `Including attempts at ${Math.round(data.attempt_weight * 100)}% weight` : 'Climbed-only comparisons'} · {data.computed_at ? 'updated ' + data.computed_at.replace('T', ' ').slice(0, 16) : 'not yet computed'}</p>
        <div class="row">
          <label class="row small" style="gap:.4rem; margin:0; cursor:pointer" title="Also count comparisons where a member had only tried one of the problems (down-weighted)">
            <input type="checkbox" bind:checked={includeAttempts} style="width:auto; accent-color: var(--accent)" /> Include attempts
          </label>
          <select bind:value={gradeFilter} style="width:auto"><option value="">All grades</option>{#each grades as g}<option>{g}</option>{/each}</select>
          <select bind:value={algo} style="width:auto">{#each algos as [v, l]}<option value={v}>{l}</option>{/each}</select>
        </div>
      </div>
      <div class="field"><input placeholder="Filter…" bind:value={q} /></div>
      <div class="tableWrap"><table>
        <thead><tr><th class="num">#</th><th>Problem</th><th>Crag</th><th class="num">Rating</th><th>Grade</th><th class="num">±</th><th>Confidence</th><th class="num">Votes</th></tr></thead>
        <tbody>
        {#each rows as r}
          <tr>
            <td class="num faint">{r.rank}</td>
            <td><strong>{r.problem.name}</strong></td>
            <td class="muted">{r.problem.crag}</td>
            <td class="num">
              {r.rating.toFixed(0)}
              {#if r.delta >= 1}<span class="mv up" title="Up {r.delta.toFixed(0)} from its {r.seed_grade} starting point of {r.seed_rating.toFixed(0)}">▲<span class="d">{r.delta.toFixed(0)}</span></span>
              {:else if r.delta <= -1}<span class="mv down" title="Down {Math.abs(r.delta).toFixed(0)} from its {r.seed_grade} starting point of {r.seed_rating.toFixed(0)}">▼<span class="d">{Math.abs(r.delta).toFixed(0)}</span></span>
              {:else}<span class="mv none"></span>{/if}
            </td>
            <td><span class="grade">{r.problem.grade}</span></td>
            <td class="num faint">{r.uncertainty == null ? '' : r.uncertainty.toFixed(0)}</td>
            <td><span class="pill {r.confidence}">{r.confidence}</span></td>
            <td class="num faint" title="{r.n_climbers} climbers">{r.n_comparisons}</td>
          </tr>
        {/each}
        </tbody>
      </table></div>
      <p class="faint small" style="margin-top: 1rem">Rating is on an Elo-like scale seeded from grade (8C 1500 · 8C+ 1750 · 9A 2000 · 9A+ 2250) and overwritten by comparisons as they accumulate. ± is one standard deviation where the model provides it. <span class="up">▲</span>/<span class="down">▼</span> show how far a problem has moved from its grade's starting rating. The global list is members-only for now.</p>
    {/if}
  {:else}
    {#if progress}
      <div class="row stats">
        <div class="card stat"><div class="big">{progress.n_done}</div><div class="muted small">climbed</div></div>
        <div class="card stat"><div class="big">{progress.n_tried}</div><div class="muted small">tried</div></div>
        <div class="card stat"><div class="big">{progress.n_done_answered} <span class="faint" style="font-size:1rem">/ {progress.n_done_pairs}</span></div><div class="muted small">climbed pairs</div></div>
        {#if progress.n_attempt_pairs}<div class="card stat"><div class="big">{progress.n_attempt_answered} <span class="faint" style="font-size:1rem">/ {progress.n_attempt_pairs}</span></div><div class="muted small">attempt pairs</div></div>{/if}
      </div>
    {/if}
    <p class="muted small" style="margin: 1rem 0 .75rem">Your problems ordered by your answers alone, next to where each sits on the global list.
      {#if session.me?.public_profile}This is <a href="/climber/{session.me.id}">public</a>.{:else}Private to you — you can make it public from your <a href="/profile">profile</a>.{/if}</p>
    {#if !mine || !mine.length}
      <p class="faint">Tick some ascents and answer a few pairs first.</p>
    {:else}
      <PersonalTable rows={mine} />
    {/if}
  {/if}
</div>

<style>
  .mv { display: inline-block; min-width: 3.2em; text-align: left; margin-left: .35rem; font-size: .75rem; }
  .mv .d { margin-left: .15rem; }
  .up, .mv.up { color: var(--ok); } .down, .mv.down { color: var(--danger); }
  .tabs { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
  .tabs button { border: none; border-radius: 0; padding: .45rem 1rem; color: var(--fg2); background: transparent; }
  .tabs button.sel { background: var(--bg3); color: var(--fg); }
  .stats { gap: .75rem; } .stat { min-width: 130px; padding: .8rem 1rem; }
  @media (max-width: 640px) { .stats { display: grid; grid-template-columns: 1fr 1fr; } .stat { min-width: 0; } .big { font-size: 1.35rem; } } .big { font-size: 1.6rem; font-family: var(--mono); line-height: 1.2; }
</style>
