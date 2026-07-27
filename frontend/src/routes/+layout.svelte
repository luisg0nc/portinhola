<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { _, isLoading } from 'svelte-i18n';
  import { setupI18n } from '$lib/i18n';

  let { children } = $props();
  let ready = $state(false);

  setupI18n();

  const publicPaths = ['/login', '/setup'];

  onMount(async () => {
    const res = await fetch('/api/auth/status');
    const status = await res.json();
    if (status.setup_required) {
      if (page.url.pathname !== '/setup') await goto('/setup');
    } else if (!status.authenticated && !publicPaths.includes(page.url.pathname)) {
      await goto('/login');
    }
    ready = true;
  });

  const tabs = [
    { href: '/', key: 'nav.dashboard', icon: '📊' },
    { href: '/bills', key: 'nav.bills', icon: '🧾' },
    { href: '/readings', key: 'nav.readings', icon: '🔢' },
    { href: '/calculator', key: 'nav.calculator', icon: '🧮' },
    { href: '/settings', key: 'nav.settings', icon: '⚙️' }
  ];

  let showNav = $derived(!publicPaths.includes(page.url.pathname));
</script>

{#if ready && !$isLoading}
  <div class="app">
    <main>{@render children()}</main>
    {#if showNav}
      <nav>
        {#each tabs as tab}
          <a href={tab.href} class:active={page.url.pathname === tab.href}>
            <span class="icon">{tab.icon}</span>
            <span class="label">{$_(tab.key)}</span>
          </a>
        {/each}
      </nav>
    {/if}
  </div>
{/if}

<style>
  :global(body) {
    margin: 0;
    font-family: system-ui, sans-serif;
    background: #f8fafc;
    color: #0f172a;
  }
  .app {
    display: flex;
    flex-direction: column;
    min-height: 100dvh;
  }
  main {
    flex: 1;
    padding: 1rem;
    padding-bottom: 4.5rem;
  }
  nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    justify-content: space-around;
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
    padding: 0.4rem 0 max(0.4rem, env(safe-area-inset-bottom));
  }
  nav a {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.1rem;
    text-decoration: none;
    color: #64748b;
    font-size: 0.7rem;
  }
  nav a.active {
    color: #0f172a;
    font-weight: 600;
  }
  .icon {
    font-size: 1.2rem;
  }
  @media (min-width: 768px) {
    .app {
      flex-direction: row;
    }
    main {
      order: 2;
      padding-bottom: 1rem;
    }
    nav {
      position: sticky;
      top: 0;
      order: 1;
      flex-direction: column;
      justify-content: flex-start;
      gap: 0.5rem;
      width: 12rem;
      height: 100dvh;
      border-top: none;
      border-right: 1px solid #e2e8f0;
      padding: 1rem 0.5rem;
    }
    nav a {
      flex-direction: row;
      gap: 0.6rem;
      font-size: 0.9rem;
      padding: 0.5rem 0.75rem;
      border-radius: 0.5rem;
      width: 100%;
      box-sizing: border-box;
    }
    nav a.active {
      background: #f1f5f9;
    }
  }
</style>
