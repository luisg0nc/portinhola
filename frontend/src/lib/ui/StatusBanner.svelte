<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    kind = 'info',
    children
  }: {
    kind?: 'success' | 'warning' | 'danger' | 'info';
    children: Snippet;
  } = $props();
</script>

<div class={`banner ${kind}`} role={kind === 'danger' ? 'alert' : 'status'}>
  {@render children()}
</div>

<style>
  .banner {
    border-radius: var(--radius-control);
    padding: 0.65rem 0.9rem;
    font-size: 0.88rem;
    margin-bottom: 0.9rem;
  }
  .banner :global(p) {
    margin: 0 0 0.4rem;
  }
  .banner :global(p:last-child) {
    margin-bottom: 0;
  }
  .success {
    background: var(--success-tint);
    color: var(--success);
  }
  .warning {
    background: var(--warning-tint);
    color: var(--warning);
  }
  .danger {
    background: var(--danger-tint);
    color: var(--danger);
  }
  .info {
    background: var(--surface-sunken);
    color: var(--ink);
  }
</style>
