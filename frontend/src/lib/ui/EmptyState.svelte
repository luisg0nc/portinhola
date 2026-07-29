<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Component } from 'svelte';
  import { Inbox } from './icons';

  let {
    icon = Inbox,
    message,
    children
  }: {
    icon?: Component;
    message: string;
    children?: Snippet;
  } = $props();

  const Icon = $derived(icon);
</script>

<div class="empty">
  <div class="disc"><Icon size={26} strokeWidth={1.8} /></div>
  <p>{message}</p>
  {#if children}
    <div class="cta">{@render children()}</div>
  {/if}
</div>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 2.5rem 1rem;
    color: var(--ink-muted);
  }
  .disc {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 3.5rem;
    height: 3.5rem;
    border-radius: 50%;
    background: var(--accent-tint);
    color: var(--accent);
    margin-bottom: 0.9rem;
  }
  p {
    margin: 0 0 1rem;
    max-width: 24rem;
  }
</style>
