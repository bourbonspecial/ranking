<script>
  import { api } from '../lib/api.js'
  let climbers = $state([]), err = $state(''), msg = $state(''), name = $state(''), email = $state('')
  $effect(() => { load() })
  async function load() { climbers = await api.get('/api/admin/climbers') }
  async function act(fn, ok) { err = ''; msg = ''; try { await fn(); msg = ok; await load() } catch (x) { err = x.message } }
  const invite = (c) => act(() => api.post(`/api/admin/climbers/${c.id}/invite`), `Invitation sent to ${c.email}`)
  const reject = (c) => act(() => api.post(`/api/admin/climbers/${c.id}/reject`), `${c.email} deactivated`)
  const admin = (c, v) => act(() => api.post(`/api/admin/climbers/${c.id}/admin?value=${v}`), 'Updated')
  const test = (c, v) => act(() => api.post(`/api/admin/climbers/${c.id}/test?value=${v}`), v ? `${c.name} is now a test user; their comparisons are excluded from the ranking` : `${c.name}'s comparisons now count`)
  const recompute = () => act(() => api.post('/api/admin/recompute'), 'Ratings recomputed')
  async function inviteNew(e) { e.preventDefault(); await act(() => api.post('/api/admin/invite', { name, email }), `Invitation sent to ${email}`); name = ''; email = '' }
  const groups = [['requested', 'Invite requests'], ['invited', 'Invited, not yet signed in'], ['active', 'Members'], ['deactivated', 'Deactivated / rejected']]
</script>

<div class="container">
  <div class="row" style="justify-content: space-between"><h1>Admin</h1><button onclick={recompute}>Recompute ratings now</button></div>
  {#if err}<p class="error">{err}</p>{/if}{#if msg}<p class="ok">{msg}</p>{/if}

  <div class="card" style="margin: 1rem 0 2rem">
    <h3>Invite someone directly</h3>
    <form class="row" onsubmit={inviteNew}>
      <input placeholder="Name" bind:value={name} required style="flex:1" />
      <input placeholder="Email" type="email" bind:value={email} required style="flex:1" />
      <button class="primary">Send invitation</button>
    </form>
  </div>

  {#each groups as [status, title]}
    {@const rows = climbers.filter(c => c.status === status)}
    <h2 style="margin-top: 1.5rem">{title} <span class="faint">({rows.length})</span></h2>
    {#if !rows.length}<p class="faint small">None.</p>{:else}
    <div class="tableWrap"><table>
      <thead><tr><th>Name</th><th>Email</th>{#if status === 'requested'}<th>Claims</th>{/if}<th class="num">Ascents</th><th class="num">Answers</th>{#if status === 'active'}<th title="Test users can use everything but their comparisons are excluded from the global ranking">Test</th>{/if}<th></th></tr></thead>
      <tbody>
      {#each rows as c}
        <tr>
          <td><a href="/admin/climber/{c.id}" title="View ascents, answers and personal ordering">{c.name}</a>{#if c.is_admin} <span class="pill">admin</span>{/if}{#if c.is_test} <span class="pill test">test</span>{/if}</td>
          <td class="mono small">{c.email}</td>
          {#if status === 'requested'}<td class="small muted">{c.request_note ?? ''}</td>{/if}
          <td class="num">{c.n_ascents}</td><td class="num">{c.n_comparisons}</td>
          {#if status === 'active'}<td><input type="checkbox" checked={c.is_test} onchange={(e) => test(c, e.target.checked)} style="width:auto; accent-color: var(--accent2)" title="Exclude this user's comparisons from the global ranking" /></td>{/if}
          <td style="white-space:nowrap; text-align:right">
            {#if status === 'requested'}<button class="primary" onclick={() => invite(c)}>Invite</button> <button class="danger" onclick={() => reject(c)}>Reject</button>
            {:else if status === 'invited'}<button onclick={() => invite(c)}>Resend</button> <button class="danger" onclick={() => reject(c)}>Revoke</button>
            {:else if status === 'active'}<button onclick={() => admin(c, !c.is_admin)}>{c.is_admin ? 'Remove admin' : 'Make admin'}</button> <button class="danger" onclick={() => reject(c)}>Deactivate</button>
            {:else}<button onclick={() => invite(c)}>Re-invite</button>{/if}
          </td>
        </tr>
      {/each}
      </tbody>
    </table></div>
    {/if}
  {/each}
</div>

<style>.pill.test { border-color: var(--accent2); color: var(--accent2); }</style>
