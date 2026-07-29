<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    href,
    tinted = false,
    children,
    ...rest
  }: {
    href?: string;
    tinted?: boolean;
    children: Snippet;
    [key: string]: unknown;
  } = $props();
</script>

{#if href}
  <a class="card link" class:tinted {href} {...rest}>{@render children()}</a>
{:else}
  <section class="card" class:tinted {...rest}>{@render children()}</section>
{/if}

<style>
  .card {
    display: block;
    background: var(--surface);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-card);
    padding: 1rem 1.1rem;
    margin-bottom: 0.9rem;
  }
  .card.tinted {
    background: var(--surface-sunken);
    box-shadow: none;
  }
  .card.link {
    text-decoration: none;
    color: inherit;
    transition:
      box-shadow 0.15s ease,
      transform 0.15s ease;
  }
  .card.link:hover {
    box-shadow: var(--shadow-raised);
    transform: translateY(-1px);
  }
</style>
