<script>
  import { api } from '../lib/api.js'
  import Problem from '../lib/Problem.svelte'
  let rows = $state([]), err = $state('')
  $effect(() => { load() })
  async function load() { rows = await api.get('/api/me/comparisons') }
  async function set(r, verdict) {
    if (r.verdict === verdict) return
    try { await api.post('/api/me/comparisons', { problem_a: r.problem_a.id, problem_b: r.problem_b.id, verdict }); r.verdict = verdict }
    catch (x) { err = x.message }
  }
</script>

<div class="container">
  <h1>My answers</h1>
  <p class="muted">Every pair you've answered. Change your mind any time — only your latest answer counts.</p>
  {#if err}<p class="error">{err}</p>{/if}
  {#if !rows.length}
    <p class="faint">Nothing yet. <a href="/compare">Start comparing →</a></p>
  {:else}
  <div class="tableWrap"><table>
    <thead><tr><th>Problem</th><th></th><th>Problem</th><th>Answered</th></tr></thead>
    <tbody>
    {#each rows as r}
      <tr>
        <td><Problem p={r.problem_a} /></td>
        <td class="ctl">
          <button class:sel={r.verdict === 'A_HARDER'} onclick={() => set(r, 'A_HARDER')} title="left was harder">◀</button>
          <button class:sel={r.verdict === 'SIMILAR'} onclick={() => set(r, 'SIMILAR')} title="very similar">=</button>
          <button class:sel={r.verdict === 'B_HARDER'} onclick={() => set(r, 'B_HARDER')} title="right was harder">▶</button>
        </td>
        <td><Problem p={r.problem_b} /></td>
        <td class="faint small mono">{r.updated_at.slice(0, 10)}</td>
      </tr>
    {/each}
    </tbody>
  </table></div>
  {/if}
</div>
<style>
  .ctl { white-space: nowrap; } .ctl button { padding: .2rem .5rem; margin: 0 .1rem; }
  .ctl button.sel { background: var(--accent); color: #111; border-color: var(--accent); }
</style>
