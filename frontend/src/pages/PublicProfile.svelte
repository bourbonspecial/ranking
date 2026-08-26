<script>
  import { api } from '../lib/api.js'
  import { route } from '../lib/router.svelte.js'
  import { session } from '../lib/session.svelte.js'
  import PersonalTable from '../lib/PersonalTable.svelte'
  import Problem from '../lib/Problem.svelte'
  import Logo from '../lib/Logo.svelte'
  let data = $state(null), err = $state('')
  let id = $derived(route.path.split('/')[2])
  $effect(() => { load(id) })
  async function load(cid) {
    data = null; err = ''
    try { data = await api.get(`/api/climbers/${cid}/public`) } catch (x) { err = x.status === 404 ? 'This profile is private or does not exist.' : x.message }
  }
  const glyph = { A_HARDER: '◀ harder', SIMILAR: '= similar', B_HARDER: 'harder ▶' }
</script>

<div class="container">
  {#if !session.me}<p class="small"><a href="/" class="brandlink"><Logo size={18} /> The List</a></p>{/if}
  {#if err}<h1>Hmm.</h1><p class="muted">{err}</p>
  {:else if data}
    <div class="eyebrow">Personal ordering</div>
    <h1>{data.name}</h1>
    <p class="muted">{data.n_done} climbed · {data.n_tried} tried · {data.n_comparisons} comparisons. Ordered by {data.name}'s own answers; the "Global" column shows where each problem sits on the members' list.</p>
    <PersonalTable rows={data.ranking} youLabel={data.name.split(' ')[0]} />

    <h2 style="margin-top: 2rem">Answers</h2>
    <div class="tableWrap"><table>
      <thead><tr><th>Problem</th><th></th><th>Problem</th><th></th></tr></thead>
      <tbody>
      {#each data.comparisons as c}
        <tr>
          <td><Problem p={c.problem_a} /></td>
          <td class="mono small muted" style="white-space:nowrap">{glyph[c.verdict]}</td>
          <td><Problem p={c.problem_b} /></td>
          <td>{#if c.kind === 'attempt'}<span class="pill none">attempt</span>{/if}</td>
        </tr>
      {/each}
      </tbody>
    </table></div>
  {/if}
</div>
<style>
  .eyebrow { font-size: .75rem; letter-spacing: .18em; text-transform: uppercase; color: var(--accent); margin-bottom: .5rem; }
  .brandlink { color: var(--accent); letter-spacing: .12em; text-transform: uppercase; font-weight: 600; font-size: .8rem; }
</style>
