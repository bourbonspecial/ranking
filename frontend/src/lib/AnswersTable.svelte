<script>
  // Read-only list of one climber's comparisons (public profile and admin view).
  import Problem from './Problem.svelte'
  let { rows } = $props()
  const glyph = { A_HARDER: '◀ harder', SIMILAR: '= similar', B_HARDER: 'harder ▶' }
</script>
{#if !rows.length}<p class="faint small">No answers yet.</p>{:else}
<div class="tableWrap"><table>
  <thead><tr><th>Problem</th><th></th><th>Problem</th><th></th><th>Answered</th></tr></thead>
  <tbody>
  {#each rows as c}
    <tr>
      <td><Problem p={c.problem_a} /></td>
      <td class="mono small muted" style="white-space:nowrap">{glyph[c.verdict]}</td>
      <td><Problem p={c.problem_b} /></td>
      <td>{#if c.kind === 'attempt'}<span class="pill none">attempt</span>{/if}</td>
      <td class="faint small mono" style="white-space:nowrap">{c.updated_at.slice(0, 10)}</td>
    </tr>
  {/each}
  </tbody>
</table></div>
{/if}
