<script>
  import { api } from '../lib/api.js'
  import Problem from '../lib/Problem.svelte'
  let queue = $state([]), progress = $state(null), err = $state(''), busy = $state(false), flash = $state(null)
  let current = $derived(queue[0] ?? null)

  $effect(() => { load(); })
  async function load() {
    [queue, progress] = await Promise.all([api.get('/api/me/pairs?limit=25'), api.get('/api/me/progress')])
  }
  async function answer(verdict) {
    if (!current || busy) return
    busy = true; err = ''
    const pair = current
    try {
      progress = await api.post('/api/me/comparisons', { problem_a: pair.problem_a.id, problem_b: pair.problem_b.id, verdict })
      flash = verdict; setTimeout(() => (flash = null), 250)
      queue = queue.slice(1)
      if (queue.length < 5) queue = [...queue, ...(await api.get('/api/me/pairs?limit=25')).filter(p => !queue.some(q => q.problem_a.id === p.problem_a.id && q.problem_b.id === p.problem_b.id))]
    } catch (x) { err = x.message } finally { busy = false }
  }
  function skip() { if (queue.length > 1) queue = [...queue.slice(1), queue[0]] }
  function key(e) {
    if (e.target.tagName === 'INPUT') return
    if (e.key === 'ArrowLeft' || e.key === '1') answer('A_HARDER')
    else if (e.key === 'ArrowDown' || e.key === '2' || e.key === '=') answer('SIMILAR')
    else if (e.key === 'ArrowRight' || e.key === '3') answer('B_HARDER')
    else if (e.key === 's') skip()
  }
</script>

<svelte:window onkeydown={key} />

<div class="container">
  <div class="row" style="justify-content: space-between; margin-bottom: 1.5rem">
    <h1>Which was harder <span class="muted">for you</span>?</h1>
    {#if progress}
      <div class="small muted mono">{progress.n_answered} / {progress.n_possible_pairs} pairs answered
        {#if !progress.ranking_unlocked} · {progress.ranking_required - progress.n_answered} more to unlock the list{/if}</div>
    {/if}
  </div>

  {#if progress && progress.n_ticked < 2}
    <div class="notice">You need at least two ascents ticked before there's anything to compare. <a href="/ticks">Add your ascents →</a></div>
  {:else if progress && !current}
    <div class="card"><h2>That's everything.</h2>
      <p class="muted">You've answered every pair on your list. Add more ascents when you have them, or <a href="/mine">review your answers</a>.</p>
      {#if progress.ranking_unlocked}<a href="/ranking" class="btn">See the list →</a>{/if}</div>
  {:else if current}
    <div class="arena" class:flash>
      <button class="side" onclick={() => answer('A_HARDER')} disabled={busy}>
        <div class="name">{current.problem_a.name}</div>
        <div class="meta"><span class="grade">{current.problem_a.grade}</span> {current.problem_a.crag}</div>
        <div class="faint small">{current.problem_a.fa_name}{current.problem_a.fa_date ? `, ${current.problem_a.fa_date}` : ''}</div>
        <div class="hint"><kbd>←</kbd> harder</div>
      </button>
      <div class="mid">
        <button class="ghost" onclick={() => answer('SIMILAR')} disabled={busy}>Very similar<br/><kbd>↓</kbd></button>
        <button class="ghost small faint" onclick={skip}>skip <kbd>s</kbd></button>
      </div>
      <button class="side" onclick={() => answer('B_HARDER')} disabled={busy}>
        <div class="name">{current.problem_b.name}</div>
        <div class="meta"><span class="grade">{current.problem_b.grade}</span> {current.problem_b.crag}</div>
        <div class="faint small">{current.problem_b.fa_name}{current.problem_b.fa_date ? `, ${current.problem_b.fa_date}` : ''}</div>
        <div class="hint">harder <kbd>→</kbd></div>
      </button>
    </div>
    {#if err}<p class="error">{err}</p>{/if}
    <p class="faint small" style="margin-top: 1.5rem">Answer for yourself, not for the consensus. You can change any answer later under <a href="/mine">My answers</a>.
      {#if progress.ranking_unlocked}<a href="/ranking">See the list →</a>{/if}</p>
  {/if}
</div>

<style>
  .arena { display: grid; grid-template-columns: 1fr auto 1fr; gap: 1rem; align-items: stretch; transition: opacity .15s; }
  .arena.flash { opacity: .4; }
  .side { text-align: left; padding: 1.5rem; border-radius: 12px; background: var(--bg2); min-height: 200px; display: flex; flex-direction: column; gap: .35rem; }
  .side:hover { border-color: var(--accent); }
  .name { font-size: 1.5rem; font-weight: 500; line-height: 1.2; }
  .meta { color: var(--fg2); }
  .hint { margin-top: auto; padding-top: 1rem; color: var(--fg3); font-size: .85rem; }
  .side:last-child .hint { text-align: right; }
  .mid { display: flex; flex-direction: column; justify-content: center; gap: .75rem; align-items: center; }
  @media (max-width: 640px) { .arena { grid-template-columns: 1fr; } .mid { flex-direction: row; } }
</style>
