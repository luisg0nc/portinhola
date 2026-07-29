<script lang="ts">
  let {
    utility,
    size = 'md',
    label
  }: {
    utility: string;
    size?: 'sm' | 'md' | 'lg';
    label?: string;
  } = $props();

  const emoji: Record<string, string> = {
    electricity: '⚡',
    gas: '🔥',
    water: '💧',
    other: '📄',
    unknown: '📄'
  };
</script>

<span class={`utility-badge ${utility} ${size}`}>
  <span class="disc">{emoji[utility] ?? '📄'}</span>
  {#if label}<span class="label">{label}</span>{/if}
</span>

<style>
  .utility-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    font-weight: 700;
  }
  .disc {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--surface-sunken);
    flex-shrink: 0;
  }
  .sm .disc {
    width: 1.5rem;
    height: 1.5rem;
    font-size: 0.75rem;
  }
  .md .disc {
    width: 2rem;
    height: 2rem;
    font-size: 0.95rem;
  }
  .lg .disc {
    width: 2.5rem;
    height: 2.5rem;
    font-size: 1.2rem;
  }
  .electricity .disc {
    background: var(--electricity-tint);
  }
  .gas .disc {
    background: var(--gas-tint);
  }
  .water .disc {
    background: var(--water-tint);
  }
  .electricity .label {
    color: var(--electricity);
  }
  .gas .label {
    color: var(--gas);
  }
  .water .label {
    color: var(--water);
  }
  .label {
    font-size: 0.9em;
  }
</style>
