<script lang="ts">
  import { onMount } from 'svelte';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { formatCents } from '$lib/money';
  import Card from '$lib/ui/Card.svelte';
  import PageHeader from '$lib/ui/PageHeader.svelte';
  import StatusBanner from '$lib/ui/StatusBanner.svelte';
  import { ChevronDown, Trophy } from '$lib/ui/icons';

  type Line = { label: string; amount_cents: number; vat_rate: number };
  type Breakdown = {
    lines: Line[];
    subtotal_cents: number;
    vat_cents: number;
    total_cents: number;
    energy_kwh: number;
    days: number;
  };
  type ResultRow = {
    tariff_id: string;
    supplier: string;
    name: string;
    option: string;
    total_cents: number;
    delta_cents: number | null;
    breakdown: Breakdown;
    valid_to: string | null;
    retrieved: string;
    conditions: string | null;
  };
  type Sp = { id: number; utility: string; identifier: string; name: string };
  type DualRow = {
    kind: 'bundle' | 'mixed' | 'current';
    supplier: string;
    name: string;
    elec_total_cents: number;
    gas_total_cents: number;
    discount_cents: number;
    total_cents: number;
    delta_cents: number | null;
    conditions: string | null;
    no_discount_data: boolean;
  };

  let utility = $state<'electricity' | 'gas' | 'dual'>('electricity');
  let dualData = $state<{
    window: { elec_kwh: number; elec_days: number; gas_kwh: number; gas_days: number };
    results: DualRow[];
  } | null>(null);
  let months = $state(12);
  let supplyPoints = $state<Sp[]>([]);
  let data = $state<{
    window: { kwh: number; days: number; coverage?: number };
    current: { tariff_id: string; total_cents: number } | null;
    results: ResultRow[];
  } | null>(null);
  let errorKey = $state('');
  let expanded = $state<string | null>(null);
  let calibration = $state<{ delta_cents: number } | null>(null);
  let potencia = $state<{
    contracted_kva: number | null;
    peak_kw: number;
    recommended_kva: number;
    saving_cents_year: number | null;
  } | null>(null);

  function sp(): Sp | undefined {
    return supplyPoints.find((s) => s.utility === utility);
  }

  async function load() {
    data = null;
    dualData = null;
    errorKey = '';
    calibration = null;
    potencia = null;
    if (utility === 'dual') {
      const dualRes = await api(`/api/calculator/dual?months=${months}`);
      if (!dualRes.ok) {
        errorKey = dualRes.status >= 500 ? 'calculator.server_error' : 'calculator.no_dual_data';
        return;
      }
      dualData = await dualRes.json();
      return;
    }
    const target = sp();
    if (!target) {
      errorKey = utility === 'gas' ? 'calculator.no_gas_data' : 'calculator.no_data';
      return;
    }
    const res = await api(
      `/api/calculator/${utility}?supply_point_id=${target.id}&months=${months}`
    );
    if (!res.ok) {
      // A server failure is not "you have no data" — don't mislead.
      errorKey =
        res.status >= 500
          ? 'calculator.server_error'
          : utility === 'gas'
            ? 'calculator.no_gas_data'
            : 'calculator.no_data';
      return;
    }
    data = await res.json();

    if (utility === 'electricity') {
      const potRes = await api(`/api/calculator/potencia?supply_point_id=${target.id}`);
      if (potRes.ok) potencia = await potRes.json();
      const billsRes = await api('/api/bills?utility=electricity');
      if (billsRes.ok) {
        const bills = await billsRes.json();
        const withPeriod = bills.find((b: { period_start: string | null }) => b.period_start);
        if (withPeriod) {
          const calRes = await api(
            `/api/calculator/calibration?supply_point_id=${target.id}&bill_id=${withPeriod.id}`
          );
          if (calRes.ok) calibration = await calRes.json();
        }
      }
    }
  }

  onMount(async () => {
    const res = await api('/api/supply-points');
    if (res.ok) supplyPoints = await res.json();
    await load();
  });

  function fmt(cents: number): string {
    return formatCents(cents, $locale ?? 'pt');
  }

  function lineLabel(label: string): string {
    const key = `calculator.line_${label}`;
    const translated = $_(key);
    return translated === key ? label : translated;
  }

  // The cheapest plan that is not the current one, for the "best deal" crown.
  let bestKey = $derived.by(() => {
    if (!data || data.results.length === 0) return null;
    const best = data.results.find((r) => data!.current?.tariff_id !== r.tariff_id);
    return best ? best.tariff_id + best.option : null;
  });
</script>

<PageHeader title={$_('calculator.title')} />

<div class="controls">
  <div class="chip-row">
    {#each ['electricity', 'gas', 'dual'] as u}
      <button
        class="chip"
        class:active={utility === u}
        onclick={() => {
          utility = u as 'electricity' | 'gas' | 'dual';
          load();
        }}
      >
        {u === 'electricity' ? '⚡' : u === 'gas' ? '🔥' : '⚡🔥'}
        {u === 'dual' ? $_('calculator.dual_tab') : $_(`dashboard.utility_${u}`)}
      </button>
    {/each}
  </div>
  {#if utility === 'electricity' || utility === 'dual'}
    <div class="chip-row">
      {#each [3, 6, 12] as m}
        <button
          class="chip"
          class:active={months === m}
          onclick={() => {
            months = m;
            load();
          }}
        >
          {$_(`calculator.months_${m}`)}
        </button>
      {/each}
    </div>
  {/if}
</div>

{#if errorKey}
  <Card><p class="muted center">{$_(errorKey)}</p></Card>
{:else if dualData}
  <p class="muted">
    ⚡ {dualData.window.elec_kwh} kWh · {dualData.window.elec_days}d
    &nbsp; 🔥 {dualData.window.gas_kwh} kWh · {dualData.window.gas_days}d
  </p>
  <ul class="results">
    {#each dualData.results as row, index}
      {@const rowKey = `dual-${index}`}
      {@const isCurrent = row.kind === 'current'}
      {@const isBest = index === 0 && !isCurrent}
      <li class:current={isCurrent} class:best={isBest}>
        {#if isBest}
          <div class="crown">
            <Trophy size={13} strokeWidth={2.4} />
            {$_('calculator.best_deal')}
          </div>
        {/if}
        <button class="row" onclick={() => (expanded = expanded === rowKey ? null : rowKey)}>
          <span class="who">
            <strong>{row.supplier}</strong>
            <span class="plan muted">{row.name}</span>
            {#if isCurrent}
              <span class="badge accent">{$_('calculator.current_plan')}</span>
            {:else if row.kind === 'mixed'}
              <span class="badge neutral">{$_('calculator.mixed_pair')}</span>
            {/if}
          </span>
          <span class="numbers">
            <span class="total money">{fmt(row.total_cents)}</span>
            {#if row.delta_cents !== null && !isCurrent}
              <span class={`delta ${row.delta_cents < 0 ? 'save' : 'more'}`}>
                {row.delta_cents < 0
                  ? $_('calculator.delta_save').replace('{amount}', fmt(-row.delta_cents))
                  : $_('calculator.delta_more').replace('{amount}', fmt(row.delta_cents))}
              </span>
            {/if}
          </span>
          <span class="chev" class:open={expanded === rowKey}>
            <ChevronDown size={16} />
          </span>
        </button>
        {#if expanded === rowKey}
          <div class="breakdown">
            <table>
              <tbody>
                <tr>
                  <td>⚡ {$_('dashboard.utility_electricity')}</td>
                  <td class="amount money">{fmt(row.elec_total_cents)}</td>
                </tr>
                <tr>
                  <td>🔥 {$_('dashboard.utility_gas')}</td>
                  <td class="amount money">{fmt(row.gas_total_cents)}</td>
                </tr>
                {#if row.discount_cents !== 0}
                  <tr class="discount-row">
                    <td>{$_('calculator.dual_discount')}</td>
                    <td class="amount money">{fmt(row.discount_cents)}</td>
                  </tr>
                {/if}
              </tbody>
            </table>
            {#if row.no_discount_data}
              <p class="muted src">{$_('calculator.no_discount_data')}</p>
            {/if}
            {#if row.conditions}
              <p class="conditions">⚠ {row.conditions}</p>
            {/if}
          </div>
        {/if}
      </li>
    {/each}
  </ul>
  <p class="muted note">{$_('calculator.staleness_note')}</p>
{:else if data}
  {#if calibration}
    {@const delta = Math.abs(calibration.delta_cents)}
    <StatusBanner kind={delta <= 50 ? 'success' : 'warning'}>
      <p>
        {$_(delta <= 50 ? 'calculator.calibration_ok' : 'calculator.calibration_warn').replace(
          '{delta}',
          fmt(delta)
        )}
      </p>
    </StatusBanner>
  {/if}
  {#if data.window.coverage !== undefined && data.window.coverage < 0.9}
    <StatusBanner kind="warning">
      <p>
        {$_('calculator.coverage_warning').replace(
          '{pct}',
          String(Math.round(data.window.coverage * 100))
        )}
      </p>
    </StatusBanner>
  {/if}

  <p class="muted">
    {data.window.kwh} kWh · {data.window.days}d
  </p>

  <ul class="results">
    {#each data.results as row}
      {@const rowKey = row.tariff_id + row.option}
      {@const isCurrent = data.current?.tariff_id === row.tariff_id}
      {@const isBest = bestKey === rowKey && !isCurrent}
      <li class:current={isCurrent} class:best={isBest}>
        {#if isBest}
          <div class="crown">
            <Trophy size={13} strokeWidth={2.4} />
            {$_('calculator.best_deal')}
          </div>
        {/if}
        <button class="row" onclick={() => (expanded = expanded === rowKey ? null : rowKey)}>
          <span class="who">
            <strong>{row.supplier}</strong>
            <span class="plan muted">{row.name} · {row.option}</span>
            {#if isCurrent}
              <span class="badge accent">{$_('calculator.current_plan')}</span>
            {/if}
          </span>
          <span class="numbers">
            <span class="total money">{fmt(row.total_cents)}</span>
            {#if row.delta_cents !== null && !isCurrent}
              <span class={`delta ${row.delta_cents < 0 ? 'save' : 'more'}`}>
                {row.delta_cents < 0
                  ? $_('calculator.delta_save').replace('{amount}', fmt(-row.delta_cents))
                  : $_('calculator.delta_more').replace('{amount}', fmt(row.delta_cents))}
              </span>
            {/if}
          </span>
          <span class="chev" class:open={expanded === rowKey}>
            <ChevronDown size={16} />
          </span>
        </button>
        {#if expanded === rowKey}
          <div class="breakdown">
            <table>
              <tbody>
                {#each row.breakdown.lines as line}
                  {#if line.amount_cents !== 0}
                    <tr>
                      <td>{lineLabel(line.label)}</td>
                      <td class="amount money">{fmt(line.amount_cents)}</td>
                    </tr>
                  {/if}
                {/each}
                <tr>
                  <td>{lineLabel('vat')}</td>
                  <td class="amount money">{fmt(row.breakdown.vat_cents)}</td>
                </tr>
              </tbody>
            </table>
            {#if row.conditions}
              <p class="conditions">⚠ {row.conditions}</p>
            {/if}
            <p class="muted src">
              {$_('calculator.prices_retrieved')} {row.retrieved}
              {#if row.valid_to}· {$_('calculator.valid_until')} {row.valid_to}{/if}
            </p>
          </div>
        {/if}
      </li>
    {/each}
  </ul>

  {#if potencia && potencia.contracted_kva}
    <Card>
      <h2>{$_('calculator.potencia_title')}</h2>
      <div class="pot-grid">
        <div>
          <span class="muted">{$_('calculator.potencia_contracted')}</span>
          <strong class="money">{potencia.contracted_kva} kVA</strong>
        </div>
        <div>
          <span class="muted">{$_('calculator.potencia_peak')}</span>
          <strong class="money">{potencia.peak_kw} kW</strong>
        </div>
        <div>
          <span class="muted">{$_('calculator.potencia_recommended')}</span>
          <strong class="money">{potencia.recommended_kva} kVA</strong>
        </div>
      </div>
      {#if potencia.saving_cents_year}
        <p class="save-note">
          {$_('calculator.potencia_saving').replace('{amount}', fmt(potencia.saving_cents_year))}
        </p>
      {:else}
        <p class="muted">{$_('calculator.potencia_ok')}</p>
      {/if}
    </Card>
  {/if}

  <p class="muted note">{$_('calculator.staleness_note')}</p>
{:else}
  <p class="muted">{$_('common.loading')}</p>
{/if}

<style>
  .controls {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    margin-bottom: 1rem;
  }
  .center {
    text-align: center;
    padding: 1rem 0;
  }
  .results {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }
  .results li {
    background: var(--surface);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-card);
    overflow: hidden;
  }
  .results li.current {
    box-shadow:
      var(--shadow-card),
      inset 0 0 0 2px var(--accent);
  }
  .crown {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    background: var(--success-tint);
    color: var(--success);
    font-size: 0.75rem;
    font-weight: 800;
    padding: 0.3rem 0.9rem;
  }
  .row {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
    padding: 0.75rem 0.9rem;
    background: none;
    border: none;
    cursor: pointer;
    text-align: left;
    font-size: 0.95rem;
    font-family: var(--font);
    color: var(--ink);
  }
  .who {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 0;
  }
  .plan {
    font-size: 0.8rem;
  }
  .who .badge {
    align-self: flex-start;
  }
  .numbers {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.15rem;
    margin-left: auto;
    flex-shrink: 0;
  }
  .total {
    font-weight: 800;
  }
  .delta {
    font-size: 0.8rem;
    font-weight: 700;
  }
  .delta.save {
    color: var(--success);
  }
  .delta.more {
    color: var(--danger);
  }
  .chev {
    display: flex;
    color: var(--ink-muted);
    transition: transform 0.15s ease;
    flex-shrink: 0;
  }
  .chev.open {
    transform: rotate(180deg);
  }
  .breakdown {
    border-top: 1px solid var(--line);
    padding: 0.6rem 0.9rem;
  }
  .breakdown table {
    width: 100%;
    font-size: 0.85rem;
    border-collapse: collapse;
  }
  .breakdown td {
    padding: 0.15rem 0;
  }
  .breakdown .amount {
    text-align: right;
  }
  .src {
    margin: 0.4rem 0 0;
  }
  .conditions {
    margin: 0.5rem 0 0;
    font-size: 0.8rem;
    color: var(--warning);
    background: var(--warning-tint);
    border-radius: var(--radius-control);
    padding: 0.35rem 0.6rem;
  }
  .results + :global(.card) {
    margin-top: 1rem;
  }
  .pot-grid {
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
  }
  .pot-grid div {
    display: flex;
    flex-direction: column;
  }
  .pot-grid strong {
    font-size: 1.1rem;
    font-weight: 800;
  }
  .save-note {
    color: var(--success);
    font-weight: 700;
    margin-bottom: 0;
  }
  .discount-row td {
    color: var(--success);
    font-weight: 700;
  }
  .note {
    margin-top: 1rem;
  }
</style>
