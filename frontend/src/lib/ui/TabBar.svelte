<script lang="ts">
  import { _ } from 'svelte-i18n';
  import type { Component } from 'svelte';
  import { House, ReceiptText, Gauge, Scale, Settings } from './icons';

  let { current }: { current: string } = $props();

  const tabs: { href: string; key: string; icon: Component }[] = [
    { href: '/', key: 'nav.dashboard', icon: House },
    { href: '/bills', key: 'nav.bills', icon: ReceiptText },
    { href: '/readings', key: 'nav.readings', icon: Gauge },
    { href: '/calculator', key: 'nav.calculator', icon: Scale },
    { href: '/settings', key: 'nav.settings', icon: Settings }
  ];

  function isActive(href: string): boolean {
    return href === '/' ? current === '/' : current.startsWith(href);
  }
</script>

<nav aria-label="Main">
  {#each tabs as tab}
    {@const Icon = tab.icon}
    {@const active = isActive(tab.href)}
    <a href={tab.href} class:active aria-current={active ? 'page' : undefined}>
      <Icon size={20} strokeWidth={active ? 2.4 : 2} />
      {#if active}<span class="label">{$_(tab.key)}</span>{/if}
    </a>
  {/each}
</nav>

<style>
  nav {
    position: fixed;
    bottom: max(0.7rem, env(safe-area-inset-bottom));
    left: 0.75rem;
    right: 0.75rem;
    display: flex;
    justify-content: space-around;
    align-items: center;
    background: var(--surface);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-raised);
    padding: 0.45rem 0.5rem;
    z-index: 30;
  }
  a {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--ink-muted);
    text-decoration: none;
    padding: 0.5rem 0.7rem;
    border-radius: var(--radius-pill);
    min-height: 40px;
    box-sizing: border-box;
  }
  a.active {
    background: var(--accent-tint);
    color: var(--accent);
  }
  .label {
    font-size: 0.78rem;
    font-weight: 700;
  }
</style>
