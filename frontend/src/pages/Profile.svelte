<script>
  import { api } from '../lib/api.js'
  import { session } from '../lib/session.svelte.js'
  let mine = $state([]), progress = $state(null)
  $effect(() => { load() })
  async function load() { [mine, progress] = await Promise.all([api.get('/api/me/ranking'), api.get('/api/me/progress')]) }
</script>

<div class="container">
  <h1>{session.me.name}</h1>
  <p class="muted">{session.me.email} {#if session.me.is_admin}· admin{/if}</p>
  {#if progress}
    <div class="row" style="margin: 1rem 0 2rem">
      <div class="card stat"><div class="big">{progress.n_done}</div><div class="muted small">climbed</div></div>
      <div class="card stat"><div class="big">{progress.n_tried}</div><div class="muted small">tried</div></div>
      <div class="card stat"><div class="big">{progress.n_done_answered}</div><div class="muted small">of {progress.n_done_pairs} climbed pairs answered</div></div>
      {#if progress.n_attempt_pairs}<div class="card stat"><div class="big">{progress.n_attempt_answered}</div><div class="muted small">of {progress.n_attempt_pairs} attempt pairs answered</div></div>{/if}
    </div>
  {/if}

  <h2>Your own ordering</h2>
  <p class="muted small">Your ascents ranked by your answers alone, next to where each sits on the global list. Private to you.</p>
  {#if !mine.length}
    <p class="faint">Tick some ascents and answer a few pairs first.</p>
  {:else}
  <div class="tableWrap"><table>
    <thead><tr><th class="num">You</th><th class="num">Global</th><th>Problem</th><th>Grade</th><th class="num">Your rating</th><th class="num">Your votes</th></tr></thead>
    <tbody>
    {#each mine as r}
      <tr>
        <td class="num">{r.rank}</td>
        <td class="num faint">{r.global_rank ?? '–'}</td>
        <td><strong>{r.problem.name}</strong> <span class="muted small">{r.problem.crag}</span> {#if r.status === 'tried'}<span class="pill none">tried</span>{/if}</td>
        <td><span class="grade">{r.problem.grade}</span></td>
        <td class="num">{r.rating.toFixed(0)}</td>
        <td class="num faint">{r.n_comparisons}</td>
      </tr>
    {/each}
    </tbody>
  </table></div>
  {/if}
</div>
<style>.stat { min-width: 140px; } .big { font-size: 1.8rem; font-family: var(--mono); }</style>
