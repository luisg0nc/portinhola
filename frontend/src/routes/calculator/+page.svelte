<script lang="ts">
  import { onMount } from 'svelte';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { formatCents } from '$lib/money';

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
  };
  type Sp = { id: number; utility: string; identifier: string; name: string };

  let utility = $state<'electricity' | 'gas'>('electricity');
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

  const icons = { electricity: '⚡', gas: '🔥' };

  function sp(): Sp | undefined {
    return supplyPoints.find((s) => s.utility === utility);
  }

  async function load() {
    data = null;
    errorKey = '';
    calibration = null;
    potencia = null;
    const target = sp();
    if (!target) {
      errorKey = utility === 'gas' ? 'calculator.no_gas_data' : 'calculator.no_data';
      return;
    }
    const res = await api(
      `/api/calculator/${utility}?supply_point_id=${target.id}&months=${months}`
    );
    if (!res.ok) {
      errorKey = utility === 'gas' ? 'calculator.no_gas_data' : 'calculator.no_data';
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
</script>

<h1>{$_('calculator.title')}</h1>

<div class="controls">
  <div class="tabs">
    {#each ['electricity', 'gas'] as u}
      <button
        class:active={utility === u}
        onclick={() => {
          utility = u as 'electricity' | 'gas';
          load();
        }}
      >
        {icons[u as 'electricity' | 'gas']}
      </button>
    {/each}
  </div>
  {#if utility === 'electricity'}
    <select bind:value={months} onchange={load}>
      <option value={3}>{$_('calculator.months_3')}</option>
      <option value={6}>{$_('calculator.months_6')}</option>
      <option value={12}>{$_('calculator.months_12')}</option>
    </select>
  {/if}
</div>

{#if errorKey}
  <p>{$_(errorKey)}</p>
{:else if data}
  {#if calibration}
    {@const delta = Math.abs(calibration.delta_cents)}
    <p class={`calibration ${delta <= 50 ? 'ok' : 'warn'}`}>
      {$_(delta <= 50 ? 'calculator.calibration_ok' : 'calculator.calibration_warn').replace(
        '{delta}',
        fmt(delta)
      )}
    </p>
  {/if}
  {#if data.window.coverage !== undefined && data.window.coverage < 0.9}
    <p class="warn-box">
      {$_('calculator.coverage_warning').replace(
        '{pct}',
        String(Math.round(data.window.coverage * 100))
      )}
    </p>
  {/if}

  <p class="muted">
    {data.window.kwh} kWh · {data.window.days}d
  </p>

  <ul class="results">
    {#each data.results as row}
      {@const rowKey = row.tariff_id + row.option}
      {@const isCurrent = data.current?.tariff_id === row.tariff_id}
      <li class:current={isCurrent}>
        <button class="row" onclick={() => (expanded = expanded === rowKey ? null : rowKey)}>
          <span class="who">
            <strong>{row.supplier}</strong>
            <span class="plan">{row.name} · {row.option}</span>
            {#if isCurrent}<span class="badge">{$_('calculator.current_plan')}</span>{/if}
          </span>
          <span class="numbers">
            <span class="total">{fmt(row.total_cents)}</span>
            {#if row.delta_cents !== null && !isCurrent}
              <span class={`delta ${row.delta_cents < 0 ? 'save' : 'more'}`}>
                {row.delta_cents < 0
                  ? $_('calculator.delta_save').replace('{amount}', fmt(-row.delta_cents))
                  : $_('calculator.delta_more').replace('{amount}', fmt(row.delta_cents))}
              </span>
            {/if}
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
                      <td class="amount">{fmt(line.amount_cents)}</td>
                    </tr>
                  {/if}
                {/each}
                <tr>
                  <td>{lineLabel('vat')}</td>
                  <td class="amount">{fmt(row.breakdown.vat_cents)}</td>
                </tr>
              </tbody>
            </table>
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
    <section class="pot card">
      <h2>{$_('calculator.potencia_title')}</h2>
      <div class="pot-grid">
        <div>
          <span class="muted">{$_('calculator.potencia_contracted')}</span>
          <strong>{potencia.contracted_kva} kVA</strong>
        </div>
        <div>
          <span class="muted">{$_('calculator.potencia_peak')}</span>
          <strong>{potencia.peak_kw} kW</strong>
        </div>
        <div>
          <span class="muted">{$_('calculator.potencia_recommended')}</span>
          <strong>{potencia.recommended_kva} kVA</strong>
        </div>
      </div>
      {#if potencia.saving_cents_year}
        <p class="save">
          {$_('calculator.potencia_saving').replace('{amount}', fmt(potencia.saving_cents_year))}
        </p>
      {:else}
        <p class="muted">{$_('calculator.potencia_ok')}</p>
      {/if}
    </section>
  {/if}

  <p class="muted note">{$_('calculator.staleness_note')}</p>
{:else}
  <p>{$_('common.loading')}</p>
{/if}

<style>
  .controls {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    margin-bottom: 0.8rem;
  }
  .tabs {
    display: flex;
    gap: 0.4rem;
  }
  .tabs button {
    border: 1px solid #cbd5e1;
    background: white;
    border-radius: 999px;
    padding: 0.3rem 0.9rem;
    cursor: pointer;
    font-size: 1rem;
  }
  .tabs button.active {
    background: #0f172a;
    border-color: #0f172a;
  }
  select {
    padding: 0.35rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.35rem;
  }
  .calibration {
    padding: 0.6rem 0.8rem;
    border-radius: 0.4rem;
    font-size: 0.9rem;
  }
  .calibration.ok {
    background: #dcfce7;
    color: #166534;
  }
  .calibration.warn {
    background: #fef9c3;
    color: #854d0e;
  }
  .warn-box {
    background: #fef9c3;
    padding: 0.5rem 0.8rem;
    border-radius: 0.4rem;
    font-size: 0.85rem;
  }
  .results {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }
  .results li {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    overflow: hidden;
  }
  .results li.current {
    border-color: #0ea5e9;
  }
  .row {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
    padding: 0.7rem 0.9rem;
    background: none;
    border: none;
    cursor: pointer;
    text-align: left;
    font-size: 0.95rem;
  }
  .who {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .plan {
    color: #64748b;
    font-size: 0.8rem;
  }
  .badge {
    align-self: flex-start;
    background: #e0f2fe;
    color: #075985;
    border-radius: 999px;
    padding: 0 0.5rem;
    font-size: 0.72rem;
  }
  .numbers {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.15rem;
  }
  .total {
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .delta {
    font-size: 0.8rem;
  }
  .delta.save {
    color: #16a34a;
  }
  .delta.more {
    color: #dc2626;
  }
  .breakdown {
    border-top: 1px solid #f1f5f9;
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
    font-variant-numeric: tabular-nums;
  }
  .src {
    margin: 0.4rem 0 0;
  }
  .muted {
    color: #94a3b8;
    font-size: 0.85rem;
  }
  .card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.6rem;
    padding: 0.9rem;
    margin-top: 1rem;
  }
  .card h2 {
    margin: 0 0 0.6rem;
    font-size: 1rem;
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
  .save {
    color: #16a34a;
    font-weight: 600;
  }
  .note {
    margin-top: 1rem;
  }
</style>
