<script>
  import { api } from '../lib/api.js'
  let data = $state(null), err = $state(''), locked = $state(null), algo = $state('bradley_terry'), q = $state(''), gradeFilter = $state('')
  let includeAttempts = $state(false)
  const algos = [['bradley_terry', 'Bradley–Terry'], ['elo', 'Elo'], ['win_rate', 'Win rate']]

  $effect(() => { load(algo, includeAttempts) })
  async function load(a, inc) {
    err = ''; locked = null
    try { data = await api.get(`/api/ranking?algo=${a}&include_attempts=${inc}`) }
    catch (x) { if (x.status === 403) locked = x.message; else err = x.message; data = null }
  }
  let rows = $derived((data?.rows ?? []).filter(r =>
    (!gradeFilter || r.problem.grade === gradeFilter) &&
    (!q || (r.problem.name + ' ' + r.problem.crag).toLowerCase().includes(q.toLowerCase()))))
  let grades = $derived([...new Set((data?.rows ?? []).map(r => r.problem.grade))])
</script>

<div class="container">
  <div class="row" style="justify-content: space-between; margin-bottom: 1rem">
    <div><h1>The list</h1>
      {#if data}<p class="muted small">{data.n_comparisons} comparisons{#if data.include_attempts}, incl. attempts at {Math.round(data.attempt_weight * 100)}% weight{/if} · {data.computed_at ? 'updated ' + data.computed_at.replace('T', ' ').slice(0, 16) : 'not yet computed'}</p>{/if}
    </div>
    <div class="row">
      <label class="row small" style="gap:.4rem; margin:0; cursor:pointer" title="Also count comparisons where a member had only tried one of the problems (down-weighted)">
        <input type="checkbox" bind:checked={includeAttempts} style="width:auto; accent-color: var(--accent)" /> Include attempts
      </label>
      <select bind:value={gradeFilter} style="width:auto"><option value="">All grades</option>{#each grades as g}<option>{g}</option>{/each}</select>
      <select bind:value={algo} style="width:auto">{#each algos as [v, l]}<option value={v}>{l}</option>{/each}</select>
    </div>
  </div>

  {#if locked}
    <div class="card"><h2>Not yet.</h2><p class="muted">{locked}</p><a href="/compare" class="btn">Compare →</a></div>
  {:else if err}<p class="error">{err}</p>
  {:else if data}
    <div class="field"><input placeholder="Filter…" bind:value={q} /></div>
    <div class="tableWrap"><table>
      <thead><tr><th class="num">#</th><th>Problem</th><th>Crag</th><th>Grade</th><th class="num">Rating</th><th class="num">±</th><th>Confidence</th><th class="num">Votes</th></tr></thead>
      <tbody>
      {#each rows as r}
        <tr>
          <td class="num faint">{r.rank}</td>
          <td><strong>{r.problem.name}</strong></td>
          <td class="muted">{r.problem.crag}</td>
          <td><span class="grade">{r.problem.grade}</span></td>
          <td class="num">{r.rating.toFixed(0)}</td>
          <td class="num faint">{r.uncertainty == null ? '' : r.uncertainty.toFixed(0)}</td>
          <td><span class="pill {r.confidence}">{r.confidence}</span></td>
          <td class="num faint" title="{r.n_climbers} climbers">{r.n_comparisons}</td>
        </tr>
      {/each}
      </tbody>
    </table></div>
    <p class="faint small" style="margin-top: 1rem">Rating is on an Elo-like scale seeded from grade (8C+ 1750 · 9A 2000 · 9A+ 2250) and overwritten by comparisons as they accumulate. ± is one standard deviation where the model provides it.</p>
  {/if}
</div>
