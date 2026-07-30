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
  import { Zap, ChevronRight, FileText, Plug, Flame } from '$lib/ui/icons';

  type UtilityCosts = {
    energy: number;
    power: number;
    fixed: number;
    tax: number;
    other: number;
    vat: number;
    total: number;
  };
  type MonthEntry = { month: string; by_utility: Record<string, UtilityCosts> };
  type YearEntry = { year: string; by_utility: Record<string, UtilityCosts> };

  const RANGES = [
    { key: '12m', months: 13 },
    { key: '24m', months: 25 },
    { key: '36m', months: 37 },
    { key: 'all', months: 240 }
  ] as const;

  let range = $state<string>('12m');
  let months = $state<MonthEntry[]>([]);
  let years = $state<YearEntry[]>([]);
  let loaded = $state(false);
  let selectedMonth = $state<string | null>(null);
  let last7Kwh = $state<number | null>(null);
  let contractedPower = $state<{ kva: number; cycle: string | null } | null>(null);
  let gasTier = $state<number | null>(null);
  let estimate = $state<{ period_start: string; kwh: number; estimated_cents: number } | null>(
    null
  );

  async function loadCosts() {
    const target = RANGES.find((r) => r.key === range) ?? RANGES[0];
    const res = await api(`/api/dashboard/costs?months=${target.months}`);
    if (res.ok) months = (await res.json()).months;
    selectedMonth = null;
    loaded = true;
  }

  function setRange(key: string) {
    range = key;
    loadCosts();
  }

  onMount(async () => {
    await loadCosts();

    const yearlyRes = await api('/api/dashboard/yearly');
    if (yearlyRes.ok) years = (await yearlyRes.json()).years;

    const spRes = await api('/api/supply-points');
    if (spRes.ok) {
      const allSps: {
        id: number;
        utility: string;
        contracts: {
          end_date: string | null;
          power_kva: number | null;
          cycle: string | null;
          gas_tier: number | null;
        }[];
      }[] = await spRes.json();
      for (const sp of allSps) {
        const open = sp.contracts.find((c) => c.end_date === null);
        if (!open) continue;
        if (sp.utility === 'electricity' && open.power_kva && !contractedPower) {
          contractedPower = { kva: open.power_kva, cycle: open.cycle };
        }
        if (sp.utility === 'gas' && open.gas_tier && gasTier === null) {
          gasTier = open.gas_tier;
        }
      }
      const sps = allSps.filter((sp: { utility: string }) => sp.utility === 'electricity');
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
  let shown = $derived(
    selectedMonth ? (months.find((m) => m.month === selectedMonth) ?? latest) : latest
  );

  function entryTotal(byUtility: Record<string, UtilityCosts>): number {
    return Object.values(byUtility).reduce((sum, u) => sum + u.total, 0);
  }

  // Average over complete months (the current month is still filling up).
  let avgMonthly = $derived.by(() => {
    const now = new Date().toISOString().slice(0, 7);
    const complete = months.filter((m) => m.month !== now);
    const pool = complete.length > 0 ? complete : months;
    if (pool.length === 0) return null;
    return Math.round(pool.reduce((sum, m) => sum + entryTotal(m.by_utility), 0) / pool.length);
  });

  const GAS_TIER_RANGES: Record<number, string> = {
    1: '0–220',
    2: '221–500',
    3: '501–1 000',
    4: '1 001–10 000'
  };

  const categoryKeys = ['energy', 'power', 'fixed', 'tax', 'other', 'vat'] as const;
  const utilityOrder = ['electricity', 'gas', 'water', 'unknown'];

  function orderedUtilities(byUtility: Record<string, UtilityCosts>): [string, UtilityCosts][] {
    return Object.entries(byUtility).sort(
      (a, b) => utilityOrder.indexOf(a[0]) - utilityOrder.indexOf(b[0])
    );
  }

  function fmt(cents: number): string {
    return formatCents(cents, $locale ?? 'pt');
  }
</script>

<PageHeader title={$_('nav.dashboard')} />

{#if estimate}
  <Card>
    <span class="kicker">{$_('consumption.estimate_title')}</span>
    <div class="hero money">~{fmt(estimate.estimated_cents)}</div>
    <span class="muted">
      {estimate.kwh.toFixed(1)} kWh · {$_('consumption.estimate_since').replace(
        '{date}',
        estimate.period_start
      )}
    </span>
  </Card>
{/if}

<div class="stat-grid">
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
  {#if avgMonthly !== null}
    <Card>
      <div class="stat-row">
        <div class="stat-body">
          <span class="kicker">{$_('dashboard.avg_monthly')}</span>
          <div class="stat-value money">{fmt(avgMonthly)}</div>
          <span class="muted">{$_(`dashboard.range_${range}`)}</span>
        </div>
      </div>
    </Card>
  {/if}
  {#if contractedPower}
    <Card href="/calculator">
      <div class="stat-row">
        <span class="stat-icon"><Plug size={20} strokeWidth={2.2} /></span>
        <div class="stat-body">
          <span class="kicker">{$_('dashboard.contracted_power')}</span>
          <div class="stat-value money">{contractedPower.kva} kVA</div>
          {#if contractedPower.cycle}
            <span class="muted">{contractedPower.cycle}</span>
          {/if}
        </div>
        <span class="chevron"><ChevronRight size={20} /></span>
      </div>
    </Card>
  {/if}
  {#if gasTier !== null}
    <Card>
      <div class="stat-row">
        <span class="stat-icon gas-icon"><Flame size={20} strokeWidth={2.2} /></span>
        <div class="stat-body">
          <span class="kicker">{$_('dashboard.gas_tier')}</span>
          <div class="stat-value money">
            {$_('dashboard.gas_tier_value').replace('{tier}', String(gasTier))}
          </div>
          {#if GAS_TIER_RANGES[gasTier]}
            <span class="muted">{GAS_TIER_RANGES[gasTier]} {$_('dashboard.m3_year')}</span>
          {/if}
        </div>
      </div>
    </Card>
  {/if}
</div>

{#if loaded && months.length === 0}
  <Card>
    <EmptyState icon={FileText} message={$_('dashboard.no_data')}>
      <Button href="/bills/upload">{$_('dashboard.upload_first')}</Button>
    </EmptyState>
  </Card>
{:else if months.length > 0}
  <Card>
    <div class="chart-head">
      <h2>{$_('dashboard.monthly_costs')}</h2>
      <div class="chip-row">
        {#each RANGES as r}
          <button class="chip" class:active={range === r.key} onclick={() => setRange(r.key)}>
            {$_(`dashboard.range_${r.key}`)}
          </button>
        {/each}
      </div>
    </div>
    <CostBars
      {months}
      selected={selectedMonth}
      onselect={(month) => (selectedMonth = selectedMonth === month ? null : month)}
    />
  </Card>

  {#if shown}
    <h2 class="section-title">
      {selectedMonth ? shown.month : `${$_('dashboard.latest_month')} — ${shown.month}`}
      {#if selectedMonth}
        <span class="muted total-inline money">{fmt(entryTotal(shown.by_utility))}</span>
      {/if}
    </h2>
    <div class="cards">
      {#each orderedUtilities(shown.by_utility) as [utility, costs]}
        <div class={`utility-card ${utility}`}>
          <UtilityBadge {utility} size="sm" label={$_(`dashboard.utility_${utility}`)} />
          <div class="total money">{fmt(costs.total)}</div>
          <ul>
            {#each categoryKeys as key}
              {#if costs[key] !== 0}
                <li>
                  <span>{key === 'vat' ? $_('bills.vat') : $_(`bills.category_${key}`)}</span>
                  <span class="money">{fmt(costs[key])}</span>
                </li>
              {/if}
            {/each}
          </ul>
        </div>
      {/each}
    </div>
  {/if}

  {#if years.length > 1}
    <Card>
      <h2>{$_('dashboard.yearly_title')}</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{$_('dashboard.year')}</th>
              {#each ['electricity', 'gas', 'water'] as utility}
                <th class="num">{$_(`dashboard.utility_${utility}`)}</th>
              {/each}
              <th class="num">{$_('bills.total')}</th>
            </tr>
          </thead>
          <tbody>
            {#each [...years].reverse() as entry}
              <tr>
                <td>{entry.year}</td>
                {#each ['electricity', 'gas', 'water'] as utility}
                  <td class="num money">
                    {entry.by_utility[utility] ? fmt(entry.by_utility[utility].total) : '—'}
                  </td>
                {/each}
                <td class="num money total-cell">{fmt(entryTotal(entry.by_utility))}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </Card>
  {/if}
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
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    gap: 0.8rem;
  }
  .stat-grid :global(.card) {
    margin-bottom: 0.9rem;
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
  .gas-icon {
    background: var(--gas-tint);
    color: var(--gas);
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
  .chart-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-bottom: 0.4rem;
  }
  .chart-head h2 {
    margin: 0;
  }
  .chart-head .chip {
    min-height: 32px;
    padding: 0.2rem 0.7rem;
    font-size: 0.78rem;
  }
  .section-title {
    margin: 1.2rem 0 0.7rem;
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
  }
  .total-inline {
    font-weight: 700;
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
  .table-wrap {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
  }
  th {
    text-align: left;
    color: var(--ink-muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  th,
  td {
    padding: 0.4rem 0.3rem;
    border-bottom: 1px solid var(--line);
  }
  .num {
    text-align: right;
  }
  .total-cell {
    font-weight: 800;
  }
  tbody tr:last-child td {
    border-bottom: none;
  }
</style>
