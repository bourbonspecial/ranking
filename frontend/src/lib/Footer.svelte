<script>
  const names = ['Matt Sparksy', 'Remus Knowles', 'Solly Kemball-Dory', 'Alex Gradenegger']
  // Fisher–Yates shuffle, fresh on every page load
  const order = [...names]
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[order[i], order[j]] = [order[j], order[i]]
  }
  const year = new Date().getFullYear()
</script>

<footer>
  © {year} {order.join(' · ')}
</footer>

<style>
  footer { text-align: center; color: var(--fg3); font-size: .75rem; padding: 2rem 1.25rem 1.5rem; border-top: 1px solid var(--line); margin-top: 3rem; }
</style>
