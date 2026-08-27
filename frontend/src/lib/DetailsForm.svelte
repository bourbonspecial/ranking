<script>
  // Self-reported demographics (issue #1): gender, height, arm span. Saved via PATCH /api/me;
  // used later for filtered lists, never shown publicly.
  import { api } from './api.js'
  import { session, refreshMe } from './session.svelte.js'
  let { compact = false, onsaved = () => {} } = $props()
  const GENDERS = [['', 'Prefer not to say / not set'], ['female', 'Female'], ['male', 'Male'], ['non_binary', 'Non-binary'], ['prefer_not_to_say', 'Prefer not to say']]
  let gender = $state(session.me?.gender ?? '')
  let height = $state(session.me?.height_cm ?? '')
  let span = $state(session.me?.arm_span_cm ?? '')
  let busy = $state(false), err = $state(''), saved = $state(false)
  let ape = $derived(height && span ? span - height : null)

  async function save(e) {
    e.preventDefault(); busy = true; err = ''; saved = false
    const num = (v) => (v === '' || v === null ? null : Number(v))
    try {
      await api.patch('/api/me', { gender, height_cm: num(height), arm_span_cm: num(span) })
      await refreshMe(); saved = true; onsaved()
    } catch (x) { err = x.message } finally { busy = false }
  }
</script>

<form onsubmit={save} class:compact>
  <div class="grid">
    <div class="field">
      <label for="d-gender">Gender</label>
      <select id="d-gender" bind:value={gender}>
        {#each GENDERS as [v, label]}{#if v !== '' || gender === ''}<option value={v}>{label}</option>{/if}{/each}
      </select>
    </div>
    <div class="field">
      <label for="d-height">Height <span class="faint">cm</span></label>
      <input id="d-height" type="number" inputmode="numeric" min="100" max="250" bind:value={height} placeholder="e.g. 178" />
    </div>
    <div class="field">
      <label for="d-span">Arm span <span class="faint">cm, fingertip to fingertip</span></label>
      <input id="d-span" type="number" inputmode="numeric" min="100" max="260" bind:value={span} placeholder="e.g. 185" />
    </div>
  </div>
  <div class="row" style="gap: .75rem; align-items: center">
    <button class="primary" disabled={busy}>Save</button>
    {#if ape !== null}<span class="small muted mono">ape index {ape > 0 ? '+' : ''}{ape} cm</span>{/if}
    {#if saved}<span class="small" style="color: var(--ok)">Saved</span>{/if}
    {#if err}<span class="error small">{err}</span>{/if}
  </div>
</form>

<style>
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: .75rem 1rem; }
  @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }
  .field { margin-bottom: .75rem; }
  label { display: block; font-size: .85rem; color: var(--fg2); margin-bottom: .3rem; }
</style>
