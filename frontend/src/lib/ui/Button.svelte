<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    variant = 'primary',
    size = 'md',
    href,
    type = 'button',
    disabled = false,
    onclick,
    children,
    ...rest
  }: {
    variant?: 'primary' | 'secondary' | 'danger';
    size?: 'sm' | 'md' | 'lg';
    href?: string;
    type?: 'button' | 'submit';
    disabled?: boolean;
    onclick?: (event: MouseEvent) => void;
    children: Snippet;
    [key: string]: unknown;
  } = $props();
</script>

{#if href}
  <a class={`btn ${variant} ${size}`} {href} {...rest}>{@render children()}</a>
{:else}
  <button class={`btn ${variant} ${size}`} {type} {disabled} {onclick} {...rest}>
    {@render children()}
  </button>
{/if}

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    border: none;
    border-radius: var(--radius-control);
    font-family: var(--font);
    font-weight: 700;
    cursor: pointer;
    text-decoration: none;
    transition: background 0.15s ease;
    min-height: 44px;
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .sm {
    padding: 0.35rem 0.75rem;
    font-size: 0.8rem;
    min-height: 36px;
  }
  .md {
    padding: 0.55rem 1rem;
    font-size: 0.9rem;
  }
  .lg {
    padding: 0.8rem 1.4rem;
    font-size: 1rem;
    width: 100%;
  }
  .primary {
    background: var(--accent);
    color: white;
  }
  .primary:hover:not(:disabled) {
    background: var(--accent-strong);
  }
  .secondary {
    background: var(--surface);
    color: var(--ink);
    box-shadow: inset 0 0 0 1.5px var(--line);
  }
  .secondary:hover:not(:disabled) {
    background: var(--surface-sunken);
  }
  .danger {
    background: var(--danger-tint);
    color: var(--danger);
  }
  .danger:hover:not(:disabled) {
    background: var(--danger);
    color: white;
  }
</style>
