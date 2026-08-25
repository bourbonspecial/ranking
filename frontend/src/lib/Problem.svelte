<script>
  let { p, showGrade = true, showCrag = true } = $props()
</script>
<span class="prob">
  <strong>{p.name}</strong>
  {#if showGrade}<span class="grade">{p.grade}</span>{/if}
  {#if showCrag && p.crag}<span class="muted small">· {p.crag}</span>{/if}
</span>
<style>.prob { display: inline-flex; gap: .45rem; align-items: baseline; flex-wrap: wrap; }</style>
