<script lang="ts">
  import { onMount } from 'svelte';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { formatCents } from '$lib/money';
  import CostBars from '$lib/CostBars.svelte';
  import Card from '$lib/ui/Card.svelte';
  import PageHeader from '$lib/ui/PageHeader.svelte';
  import EmptyState from '$lib/ui/EmptyState.svelte';
  import UtilityBadge from '$lib/ui/UtilityBadge.svelte';
  import Button from '$lib/ui/Button.svelte';
  import { Zap, ChevronRight, FileText } from '$lib/ui/icons';

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
  let last7Kwh = $state<number | null>(null);
  let estimate = $state<{ period_start: string; kwh: number; estimated_cents: number } | null>(
    null
  );

  onMount(async () => {
    const res = await api('/api/dashboard/costs?months=13');
    if (res.ok) months = (await res.json()).months;
    loaded = true;

    const spRes = await api('/api/supply-points');
    if (spRes.ok) {
      const sps = (await spRes.json()).filter(
        (sp: { utility: string }) => sp.utility === 'electricity'
      );
      if (sps.length > 0) {
        const end = new Date();
        const start = new Date(end.getTime() - 7 * 86400000);
        const rangeRes = await api(
          `/api/consumption/range?supply_point_id=${sps[0].id}` +
            `&start=${start.toISOString()}&end=${end.toISOString()}`
        );
        if (rangeRes.ok) {
          const rows: { kwh: number }[] = await rangeRes.json();
          if (rows.length > 0) last7Kwh = rows.reduce((sum, r) => sum + r.kwh, 0);
        }
        const estRes = await api(`/api/dashboard/estimate?supply_point_id=${sps[0].id}`);
        if (estRes.ok) estimate = await estRes.json();
      }
    }
  });

  let latest = $derived(months.at(-1) ?? null);

  const categoryKeys = ['energy', 'power', 'fixed', 'tax', 'other'] as const;
</script>

<PageHeader title={$_('nav.dashboard')} />

{#if estimate}
  <Card>
    <span class="kicker">{$_('consumption.estimate_title')}</span>
    <div class="hero money">~{formatCents(estimate.estimated_cents, $locale ?? 'pt')}</div>
    <span class="muted">
      {estimate.kwh.toFixed(1)} kWh · {$_('consumption.estimate_since').replace(
        '{date}',
        estimate.period_start
      )}
    </span>
  </Card>
{/if}

{#if last7Kwh !== null}
  <Card href="/consumption">
    <div class="stat-row">
      <span class="stat-icon"><Zap size={20} strokeWidth={2.2} /></span>
      <div class="stat-body">
        <span class="kicker">{$_('consumption.last7')}</span>
        <div class="stat-value money">{last7Kwh.toFixed(1)} kWh</div>
      </div>
      <span class="chevron"><ChevronRight size={20} /></span>
    </div>
  </Card>
{/if}

{#if loaded && months.length === 0}
  <Card>
    <EmptyState icon={FileText} message={$_('dashboard.no_data')}>
      <Button href="/bills/upload">{$_('dashboard.upload_first')}</Button>
    </EmptyState>
  </Card>
{:else if months.length > 0}
  {#if latest}
    <h2 class="section-title">{$_('dashboard.latest_month')} — {latest.month}</h2>
    <div class="cards">
      {#each Object.entries(latest.by_utility) as [utility, costs]}
        <div class={`utility-card ${utility}`}>
          <UtilityBadge {utility} size="sm" label={$_(`dashboard.utility_${utility}`)} />
          <div class="total money">{formatCents(costs.total, $locale ?? 'pt')}</div>
          <ul>
            {#each categoryKeys as key}
              {#if costs[key] !== 0}
                <li>
                  <span>{$_(`bills.category_${key}`)}</span>
                  <span class="money">{formatCents(costs[key], $locale ?? 'pt')}</span>
                </li>
              {/if}
            {/each}
          </ul>
        </div>
      {/each}
    </div>
  {/if}

  <Card>
    <h2>{$_('dashboard.monthly_costs')}</h2>
    <CostBars {months} />
  </Card>
{/if}

<style>
  .kicker {
    display: block;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink-muted);
    margin-bottom: 0.2rem;
  }
  .hero {
    font-size: 1.9rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.2;
  }
  .stat-row {
    display: flex;
    align-items: center;
    gap: 0.8rem;
  }
  .stat-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.4rem;
    height: 2.4rem;
    border-radius: 50%;
    background: var(--electricity-tint);
    color: var(--electricity);
    flex-shrink: 0;
  }
  .stat-body {
    flex: 1;
  }
  .stat-value {
    font-size: 1.3rem;
    font-weight: 800;
  }
  .chevron {
    color: var(--ink-muted);
    display: flex;
  }
  .section-title {
    margin: 1.2rem 0 0.7rem;
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    gap: 0.8rem;
    margin-bottom: 0.9rem;
  }
  .utility-card {
    border-radius: var(--radius-card);
    padding: 0.9rem 1rem;
  }
  .utility-card.electricity {
    background: var(--electricity-tint);
  }
  .utility-card.gas {
    background: var(--gas-tint);
  }
  .utility-card.water {
    background: var(--water-tint);
  }
  .utility-card:not(.electricity):not(.gas):not(.water) {
    background: var(--surface-sunken);
  }
  .utility-card .total {
    font-size: 1.45rem;
    font-weight: 800;
    margin: 0.4rem 0 0.5rem;
  }
  .electricity .total {
    color: var(--electricity);
  }
  .gas .total {
    color: var(--gas);
  }
  .water .total {
    color: var(--water);
  }
  .utility-card ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.83rem;
    color: var(--ink);
    opacity: 0.85;
  }
  .utility-card li {
    display: flex;
    justify-content: space-between;
  }
</style>
