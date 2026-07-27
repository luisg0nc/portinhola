<script lang="ts">
  import { onMount } from 'svelte';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { formatCents } from '$lib/money';
  import CostBars from '$lib/CostBars.svelte';

  type UtilityCosts = {
    energy: number;
    power: number;
    fixed: number;
    tax: number;
    other: number;
    total: number;
  };
  type MonthEntry = { month: string; by_utility: Record<string, UtilityCosts> };

  let months = $state<MonthEntry[]>([]);
  let loaded = $state(false);

  onMount(async () => {
    const res = await api('/api/dashboard/costs?months=13');
    if (res.ok) months = (await res.json()).months;
    loaded = true;
  });

  let latest = $derived(months.at(-1) ?? null);

  const categoryKeys = ['energy', 'power', 'fixed', 'tax', 'other'] as const;
  const icons: Record<string, string> = {
    electricity: '⚡',
    gas: '🔥',
    water: '💧',
    unknown: '📄'
  };
</script>

<h1>{$_('nav.dashboard')}</h1>

{#if loaded && months.length === 0}
  <p>{$_('dashboard.no_data')}</p>
  <a class="button" href="/bills/upload">{$_('dashboard.upload_first')}</a>
{:else if months.length > 0}
  <section class="card">
    <h2>{$_('dashboard.monthly_costs')}</h2>
    <CostBars {months} />
  </section>

  {#if latest}
    <h2 class="latest">{$_('dashboard.latest_month')} — {latest.month}</h2>
    <div class="cards">
      {#each Object.entries(latest.by_utility) as [utility, costs]}
        <section class="card utility">
          <h3>{icons[utility]} {$_(`dashboard.utility_${utility}`)}</h3>
          <div class="total">{formatCents(costs.total, $locale ?? 'pt')}</div>
          <ul>
            {#each categoryKeys as key}
              {#if costs[key] !== 0}
                <li>
                  <span>{$_(`bills.category_${key}`)}</span>
                  <span>{formatCents(costs[key], $locale ?? 'pt')}</span>
                </li>
              {/if}
            {/each}
          </ul>
        </section>
      {/each}
    </div>
  {/if}
{/if}

<style>
  .card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.6rem;
    padding: 1rem;
    margin-bottom: 1rem;
  }
  .card h2,
  .card h3 {
    margin: 0 0 0.5rem;
    font-size: 1rem;
  }
  .latest {
    font-size: 1.05rem;
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: 0.8rem;
  }
  .utility .total {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
  }
  .utility ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.85rem;
    color: #475569;
  }
  .utility li {
    display: flex;
    justify-content: space-between;
  }
  .button {
    display: inline-block;
    background: #0f172a;
    color: white;
    padding: 0.6rem 1rem;
    border-radius: 0.4rem;
    text-decoration: none;
  }
</style>
