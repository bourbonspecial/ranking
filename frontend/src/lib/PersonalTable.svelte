<script>
  let { rows, youLabel = 'You' } = $props()
</script>
<div class="tableWrap"><table>
  <thead><tr><th class="num">{youLabel}</th><th class="num">Global</th><th>Problem</th><th>Grade</th><th class="num">Rating</th><th class="num">Votes</th></tr></thead>
  <tbody>
  {#each rows as r}
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
