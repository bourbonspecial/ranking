<script>
  let { size = 22, bg = false } = $props()
</script>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width={size} height={size} aria-hidden="true" class="logo">
  {#if bg}<rect width="64" height="64" rx="14" fill="#0b0c0e"/>{/if}
  <rect x="24" y="13" width="16" height="10" rx="5" fill="currentColor"/>
  <rect x="19" y="27" width="26" height="10" rx="5" fill="currentColor"/>
  <rect x="14" y="41" width="36" height="10" rx="5" fill="currentColor"/>
</svg>
<style>.logo { display: inline-block; vertical-align: middle; color: var(--accent); flex-shrink: 0; }</style>
