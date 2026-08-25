<script>
  import { api } from '../lib/api.js'
  let queue = $state([]), progress = $state(null), err = $state(''), busy = $state(false), flash = $state(null)
  let attemptsOk = $state(false)   // user has opted in to comparing problems they've only tried
  let current = $derived(queue[0] ?? null)
  let needOptIn = $derived(current?.kind === 'attempt' && !attemptsOk)

  $effect(() => { load(); })
  async function load() {
    [queue, progress] = await Promise.all([api.get('/api/me/pairs?limit=25'), api.get('/api/me/progress')])
  }
  async function refill() {
    const more = await api.get('/api/me/pairs?limit=25')
    queue = [...queue, ...more.filter(p => !queue.some(q => q.problem_a.id === p.problem_a.id && q.problem_b.id === p.problem_b.id))]
  }
  async function answer(verdict) {
    if (!current || busy || needOptIn) return
    busy = true; err = ''
    const pair = current
    try {
      progress = await api.post('/api/me/comparisons', { problem_a: pair.problem_a.id, problem_b: pair.problem_b.id, verdict })
      flash = verdict; setTimeout(() => (flash = null), 250)
      queue = queue.slice(1)
      if (queue.length < 5) await refill()
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

{#snippet card(p, status, side)}
  {@const verdict = side === 'a' ? 'A_HARDER' : 'B_HARDER'}
  <button class="side" class:tried={status === 'tried'} onclick={() => answer(verdict)} disabled={busy}>
    <div class="name">{p.name}</div>
    <div class="meta"><span class="grade">{p.grade}</span> {p.crag}</div>
    <div class="faint small">{p.fa_name}{p.fa_date ? `, ${p.fa_date}` : ''}</div>
    {#if status === 'tried'}<div class="badge">Tried, not done</div>{/if}
    <div class="hint" style:text-align={side === 'b' ? 'right' : 'left'}>{#if side === 'a'}<kbd>←</kbd> harder{:else}harder <kbd>→</kbd>{/if}</div>
  </button>
{/snippet}

<div class="container">
  <div class="row" style="justify-content: space-between; margin-bottom: 1.5rem">
    <h1>Which was harder <span class="muted">for you</span>?</h1>
    {#if progress}
      <div class="small muted mono">
        {progress.n_done_answered} / {progress.n_done_pairs} climbed pairs
        {#if progress.n_attempt_pairs} · {progress.n_attempt_answered} / {progress.n_attempt_pairs} attempts{/if}
        {#if !progress.ranking_unlocked} · {progress.ranking_required - progress.n_done_answered} more to unlock the list{/if}
      </div>
    {/if}
  </div>

  {#if progress && progress.n_done < 2}
    <div class="notice">You need at least two <strong>climbed</strong> problems before there's anything to compare. <a href="/ticks">Update your ascents →</a></div>
  {:else if progress && !current}
    <div class="card"><h2>That's everything.</h2>
      <p class="muted">You've answered every pair on your list. Add more ascents when you have them, or <a href="/mine">review your answers</a>.</p>
      {#if progress.ranking_unlocked}<a href="/ranking" class="btn">See the list →</a>{/if}</div>
  {:else if needOptIn}
    <div class="card">
      <h2>You've compared everything you've climbed.</h2>
      <p class="muted">You also have {progress.n_attempt_pairs - progress.n_attempt_answered} pair{progress.n_attempt_pairs - progress.n_attempt_answered === 1 ? '' : 's'} involving problems you've <strong>tried but not done</strong>.
        You can compare those too — how hard did they feel against things you have climbed? These answers carry less weight in the list, and members can choose whether to include them at all.</p>
      <div class="row">
        <button class="primary" onclick={() => (attemptsOk = true)}>Continue with attempts</button>
        {#if progress.ranking_unlocked}<a href="/ranking" class="btn">See the list instead →</a>{/if}
      </div>
    </div>
  {:else if current}
    {#if current.kind === 'attempt'}<div class="notice small">This pair involves a problem you've tried but not climbed. Answer from how it felt; it counts for less than a comparison between two ascents.</div>{/if}
    <div class="arena" class:flash>
      {@render card(current.problem_a, current.status_a, 'a')}
      <div class="mid">
        <button class="ghost" onclick={() => answer('SIMILAR')} disabled={busy}>Very similar<br/><kbd>↓</kbd></button>
        <button class="ghost small faint" onclick={skip}>skip <kbd>s</kbd></button>
      </div>
      {@render card(current.problem_b, current.status_b, 'b')}
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
  .side.tried { border-style: dashed; }
  .name { font-size: 1.5rem; font-weight: 500; line-height: 1.2; }
  .meta { color: var(--fg2); }
  .badge { align-self: flex-start; font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; color: var(--fg2); border: 1px dashed var(--fg3); border-radius: 999px; padding: .1rem .5rem; margin-top: .25rem; }
  .hint { margin-top: auto; padding-top: 1rem; color: var(--fg3); font-size: .85rem; }
  .mid { display: flex; flex-direction: column; justify-content: center; gap: .75rem; align-items: center; }
  @media (max-width: 640px) { .arena { grid-template-columns: 1fr; } .mid { flex-direction: row; } }
</style>
