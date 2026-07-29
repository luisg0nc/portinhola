<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { _, isLoading } from 'svelte-i18n';
  import { setupI18n } from '$lib/i18n';
  import '$lib/ui/app.css';
  import TabBar from '$lib/ui/TabBar.svelte';
  import Fab from '$lib/ui/Fab.svelte';
  import { House, ReceiptText, Gauge, Scale, Settings, Plus } from '$lib/ui/icons';

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

  const sideTabs = [
    { href: '/', key: 'nav.dashboard', icon: House },
    { href: '/bills', key: 'nav.bills', icon: ReceiptText },
    { href: '/readings', key: 'nav.readings', icon: Gauge },
    { href: '/calculator', key: 'nav.calculator', icon: Scale },
    { href: '/settings', key: 'nav.settings', icon: Settings }
  ];

  function isActive(href: string): boolean {
    return href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(href);
  }

  let showNav = $derived(!publicPaths.includes(page.url.pathname));
</script>

{#if ready && !$isLoading}
  <div class="app">
    {#if showNav}
      <aside>
        <a class="wordmark" href="/">Portinhola</a>
        <a class="report" href="/readings/new">
          <Plus size={18} strokeWidth={2.6} />
          {$_('readings.new_reading')}
        </a>
        <nav aria-label="Main">
          {#each sideTabs as tab}
            {@const Icon = tab.icon}
            {@const active = isActive(tab.href)}
            <a href={tab.href} class:active aria-current={active ? 'page' : undefined}>
              <Icon size={18} strokeWidth={active ? 2.4 : 2} />
              {$_(tab.key)}
            </a>
          {/each}
        </nav>
      </aside>
    {/if}
    <main>
      <div class="content">{@render children()}</div>
    </main>
    {#if showNav && page.url.pathname !== '/readings/new'}
      <div class="mobile-only"><Fab /></div>
    {/if}
    {#if showNav}
      <div class="mobile-only"><TabBar current={page.url.pathname} /></div>
    {/if}
  </div>
{/if}

<style>
  .app {
    display: flex;
    min-height: 100dvh;
  }
  aside {
    display: none;
  }
  main {
    flex: 1;
    min-width: 0;
    padding: 1rem;
    padding-bottom: 6.5rem;
  }
  .content {
    max-width: 60rem;
    margin: 0 auto;
  }

  @media (min-width: 768px) {
    .mobile-only {
      display: none;
    }
    main {
      padding: 1.5rem 2rem;
    }
    aside {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      position: sticky;
      top: 0;
      width: 13.5rem;
      height: 100dvh;
      box-sizing: border-box;
      padding: 1.25rem 0.9rem;
      background: var(--surface);
      box-shadow: var(--shadow-card);
    }
    .wordmark {
      font-size: 1.15rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      color: var(--ink);
      text-decoration: none;
      padding: 0.25rem 0.75rem 1rem;
    }
    .report {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      background: var(--accent);
      color: white;
      border-radius: var(--radius-control);
      padding: 0.6rem 0.75rem;
      font-size: 0.88rem;
      font-weight: 700;
      text-decoration: none;
      margin-bottom: 0.9rem;
      transition: background 0.15s ease;
    }
    .report:hover {
      background: var(--accent-strong);
    }
    aside nav {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }
    aside nav a {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      color: var(--ink-muted);
      text-decoration: none;
      font-size: 0.9rem;
      font-weight: 600;
      padding: 0.55rem 0.75rem;
      border-radius: var(--radius-control);
    }
    aside nav a:hover {
      background: var(--surface-sunken);
      color: var(--ink);
    }
    aside nav a.active {
      background: var(--accent-tint);
      color: var(--accent);
    }
  }
</style>
