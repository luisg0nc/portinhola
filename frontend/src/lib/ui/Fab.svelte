<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { Plus } from './icons';
</script>

<a class="fab" href="/readings/new" aria-label={$_('readings.new_reading')}>
  <Plus size={26} strokeWidth={2.4} />
</a>

<style>
  .fab {
    position: fixed;
    right: 1rem;
    bottom: calc(max(0.7rem, env(safe-area-inset-bottom)) + 4.2rem);
    width: 3.4rem;
    height: 3.4rem;
    border-radius: 50%;
    background: var(--accent);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    box-shadow: 0 4px 12px rgba(194, 84, 46, 0.4);
    z-index: 40;
    transition: background 0.15s ease;
  }
  .fab:hover {
    background: var(--accent-strong);
  }
</style>
