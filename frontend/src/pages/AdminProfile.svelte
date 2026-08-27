<script>
  // Read-only view of one member for admins: account details, personal ordering, answers.
  import { api } from '../lib/api.js'
  import { route } from '../lib/router.svelte.js'
  import PersonalTable from '../lib/PersonalTable.svelte'
  import AnswersTable from '../lib/AnswersTable.svelte'
  let data = $state(null), err = $state('')
  let id = $derived(route.path.split('/')[3])
  $effect(() => { load(id) })
  async function load(cid) {
    data = null; err = ''
    try { data = await api.get(`/api/admin/climbers/${cid}/profile`) } catch (x) { err = x.status === 404 ? 'No such member.' : x.message }
  }
</script>

<div class="container">
  <p class="small"><a href="/admin">← Admin</a></p>
  {#if err}<h1>Hmm.</h1><p class="muted">{err}</p>
  {:else if data}
    <div class="eyebrow">Member · read-only</div>
    <h1>{data.name}
      {#if data.is_admin} <span class="pill">admin</span>{/if}
      {#if data.is_test} <span class="pill test">test</span>{/if}
      {#if data.status !== 'active'} <span class="pill none">{data.status}</span>{/if}
    </h1>
    <p class="muted">
      <span class="mono">{data.email}</span> · profile {data.public_profile ? 'public' : 'private'}
      {#if data.public_profile} (<a href="/climber/{data.id}">view as members see it</a>){/if}
    </p>
    <p class="muted">{data.n_done} climbed · {data.n_tried} tried · {data.n_comparisons} answers{#if data.updated_at}, last on {data.updated_at.slice(0, 10)}{/if}.</p>

    <h2 style="margin-top: 1.5rem">Ascents and personal ordering</h2>
    {#if !data.ranking.length}<p class="faint small">Nothing ticked yet.</p>
    {:else}<PersonalTable rows={data.ranking} youLabel={data.name.split(' ')[0]} />{/if}

    <h2 style="margin-top: 2rem">Answers</h2>
    <AnswersTable rows={data.comparisons} />
  {/if}
</div>
<style>
  .eyebrow { font-size: .75rem; letter-spacing: .18em; text-transform: uppercase; color: var(--accent); margin-bottom: .5rem; }
  .pill.test { border-color: var(--accent2); color: var(--accent2); }
</style>
