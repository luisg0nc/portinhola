<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import uPlot from 'uplot';
  import { api } from '$lib/api';
  import UPlotChart from '$lib/charts/UPlotChart.svelte';

  type View = 'day' | 'month' | 'year' | 'compare';
  type Sp = { id: number; identifier: string; name: string };

  let view = $state<View>('day');
  let supplyPoints = $state<Sp[]>([]);
  let spId = $state<number | null>(null);
  let hasData = $state(false);
  let statusText = $state('');

  const today = new Date();
  let dayDate = $state(today.toISOString().slice(0, 10));
  let monthValue = $state(today.toISOString().slice(0, 7));
  let yearValue = $state(today.getFullYear());
  let compareStartA = $state('');
  let compareStartB = $state('');
  let compareDays = $state(7);

  let dayData = $state<uPlot.AlignedData | null>(null);
  let monthData = $state<uPlot.AlignedData | null>(null);
  let yearData = $state<uPlot.AlignedData | null>(null);
  let compareData = $state<uPlot.AlignedData | null>(null);
  let totalLabel = $state('');
  let importMessage = $state('');

  const lineOpts = (label: string) => ({
    scales: { x: { time: true } },
    series: [
      {},
      { label, stroke: '#0ea5e9', width: 2, fill: 'rgba(14,165,233,0.12)' }
    ]
  });

  const barOpts = (label: string) => ({
    scales: { x: { time: true } },
    series: [
      {},
      {
        label,
        stroke: '#0ea5e9',
        fill: '#0ea5e9',
        paths: uPlot.paths!.bars!({ size: [0.6, 100] })
      }
    ]
  });

  const compareOpts = {
    scales: { x: { time: false } },
    series: [
      {},
      { label: 'A', stroke: '#0ea5e9', width: 2 },
      { label: 'B', stroke: '#f59e0b', width: 2 }
    ]
  };

  onMount(async () => {
    const res = await api('/api/supply-points');
    if (res.ok) {
      const all = await res.json();
      supplyPoints = all.filter((sp: { utility: string }) => sp.utility === 'electricity');
      if (supplyPoints.length > 0) {
        spId = supplyPoints[0].id;
        await checkStatus();
        await load();
      }
    }
  });

  async function checkStatus() {
    if (spId === null) return;
    const res = await api(`/api/consumption/status?supply_point_id=${spId}`);
    if (res.ok) {
      const s = await res.json();
      hasData = s.count > 0;
      statusText = hasData ? `${s.first_ts.slice(0, 10)} → ${s.last_ts.slice(0, 10)}` : '';
    }
  }

  async function load() {
    if (spId === null) return;
    if (view === 'day') {
      const res = await api(`/api/consumption/day?supply_point_id=${spId}&date=${dayDate}`);
      const rows: { ts: string; kwh: number }[] = res.ok ? await res.json() : [];
      const total = rows.reduce((sum, r) => sum + r.kwh, 0);
      totalLabel = `${total.toFixed(2)} kWh`;
      dayData = [
        rows.map((r) => new Date(r.ts).getTime() / 1000),
        rows.map((r) => r.kwh * 4)
      ];
    } else if (view === 'month') {
      const res = await api(`/api/consumption/month?supply_point_id=${spId}&month=${monthValue}`);
      const rows: { date: string; kwh: number }[] = res.ok ? await res.json() : [];
      totalLabel = `${rows.reduce((sum, r) => sum + r.kwh, 0).toFixed(1)} kWh`;
      monthData = [
        rows.map((r) => new Date(r.date + 'T12:00:00').getTime() / 1000),
        rows.map((r) => r.kwh)
      ];
    } else if (view === 'year') {
      const res = await api(`/api/consumption/year?supply_point_id=${spId}&year=${yearValue}`);
      const rows: { month: string; kwh: number }[] = res.ok ? await res.json() : [];
      totalLabel = `${rows.reduce((sum, r) => sum + r.kwh, 0).toFixed(0)} kWh`;
      yearData = [
        rows.map((r) => new Date(r.month + '-15T12:00:00').getTime() / 1000),
        rows.map((r) => r.kwh)
      ];
    } else if (view === 'compare' && compareStartA && compareStartB) {
      const fetchRange = async (start: string) => {
        const startIso = new Date(start + 'T00:00:00').toISOString();
        const end = new Date(new Date(start + 'T00:00:00').getTime() + compareDays * 86400000);
        const res = await api(
          `/api/consumption/range?supply_point_id=${spId}&start=${startIso}&end=${end.toISOString()}`
        );
        return res.ok ? ((await res.json()) as { kwh: number }[]) : [];
      };
      const [seriesA, seriesB] = await Promise.all([
        fetchRange(compareStartA),
        fetchRange(compareStartB)
      ]);
      const slots = Math.max(seriesA.length, seriesB.length);
      compareData = [
        Array.from({ length: slots }, (_, i) => i),
        Array.from({ length: slots }, (_, i) => (seriesA[i] ? seriesA[i].kwh * 4 : null)),
        Array.from({ length: slots }, (_, i) => (seriesB[i] ? seriesB[i].kwh * 4 : null))
      ];
      const totalA = seriesA.reduce((sum, r) => sum + r.kwh, 0);
      const totalB = seriesB.reduce((sum, r) => sum + r.kwh, 0);
      totalLabel = `A ${totalA.toFixed(1)} kWh · B ${totalB.toFixed(1)} kWh`;
    }
  }

  function setView(v: View) {
    view = v;
    load();
  }

  function shiftDay(delta: number) {
    const d = new Date(dayDate + 'T12:00:00');
    d.setDate(d.getDate() + delta);
    dayDate = d.toISOString().slice(0, 10);
    load();
  }

  function shiftMonth(delta: number) {
    const [y, m] = monthValue.split('-').map(Number);
    const d = new Date(y, m - 1 + delta, 15);
    monthValue = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    load();
  }

  function onMonthBarClick(xValue: number) {
    dayDate = new Date(xValue * 1000).toISOString().slice(0, 10);
    setView('day');
  }

  async function onImportFile(event: Event) {
    importMessage = '';
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || spId === null) return;
    const form = new FormData();
    form.append('file', file);
    form.append('supply_point_id', String(spId));
    const res = await fetch('/api/consumption/import', { method: 'POST', body: form });
    if (res.ok) {
      const body = await res.json();
      importMessage = $_('consumption.import_ok')
        .replace('{inserted}', body.inserted)
        .replace('{updated}', body.updated);
      await checkStatus();
      await load();
    } else if (res.status === 422) {
      const detail = (await res.json()).detail;
      importMessage =
        detail === 'cpe_mismatch' ? $_('consumption.cpe_mismatch') : $_('consumption.import_failed');
    } else {
      importMessage = $_('consumption.import_failed');
    }
    input.value = '';
  }
</script>

<h1>{$_('consumption.title')}</h1>

{#if supplyPoints.length > 1}
  <select bind:value={spId} onchange={() => (checkStatus(), load())}>
    {#each supplyPoints as sp}
      <option value={sp.id}>{sp.name || sp.identifier}</option>
    {/each}
  </select>
{/if}

<div class="tabs">
  {#each ['day', 'month', 'year', 'compare'] as v}
    <button class:active={view === v} onclick={() => setView(v as View)}>
      {$_(`consumption.${v}`)}
    </button>
  {/each}
</div>

{#if !hasData}
  <p>{$_('consumption.no_data')}</p>
{:else}
  <p class="muted">{statusText} · {$_('consumption.kwh_total')}: <strong>{totalLabel}</strong></p>

  {#if view === 'day'}
    <div class="nav">
      <button onclick={() => shiftDay(-1)}>←</button>
      <input type="date" bind:value={dayDate} onchange={load} />
      <button onclick={() => shiftDay(1)}>→</button>
    </div>
    {#if dayData}
      <UPlotChart data={dayData} options={lineOpts('kW')} />
    {/if}
  {:else if view === 'month'}
    <div class="nav">
      <button onclick={() => shiftMonth(-1)}>←</button>
      <input type="month" bind:value={monthValue} onchange={load} />
      <button onclick={() => shiftMonth(1)}>→</button>
    </div>
    {#if monthData}
      <UPlotChart data={monthData} options={barOpts('kWh')} onclickx={onMonthBarClick} />
    {/if}
  {:else if view === 'year'}
    <div class="nav">
      <button onclick={() => (yearValue--, load())}>←</button>
      <span class="year">{yearValue}</span>
      <button onclick={() => (yearValue++, load())}>→</button>
    </div>
    {#if yearData}
      <UPlotChart data={yearData} options={barOpts('kWh')} />
    {/if}
  {:else}
    <div class="nav compare">
      <label>{$_('consumption.period_a')} <input type="date" bind:value={compareStartA} onchange={load} /></label>
      <label>{$_('consumption.period_b')} <input type="date" bind:value={compareStartB} onchange={load} /></label>
      <select bind:value={compareDays} onchange={load}>
        <option value={1}>1d</option>
        <option value={7}>7d</option>
        <option value={30}>30d</option>
      </select>
    </div>
    {#if compareData}
      <UPlotChart data={compareData} options={compareOpts} />
    {/if}
  {/if}
{/if}

<section class="import">
  <h2>{$_('consumption.import_file')}</h2>
  <input type="file" accept=".xlsx" onchange={onImportFile} />
  {#if importMessage}<p>{importMessage}</p>{/if}
</section>

<style>
  .tabs {
    display: flex;
    gap: 0.4rem;
    margin: 0.8rem 0;
  }
  .tabs button {
    border: 1px solid #cbd5e1;
    background: white;
    border-radius: 999px;
    padding: 0.3rem 0.9rem;
    cursor: pointer;
  }
  .tabs button.active {
    background: #0f172a;
    color: white;
    border-color: #0f172a;
  }
  .nav {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin-bottom: 0.6rem;
    flex-wrap: wrap;
  }
  .nav button {
    border: 1px solid #cbd5e1;
    background: white;
    border-radius: 0.35rem;
    padding: 0.3rem 0.7rem;
    cursor: pointer;
  }
  .nav input,
  .nav select {
    padding: 0.35rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.35rem;
  }
  .year {
    font-weight: 700;
    padding: 0 0.5rem;
  }
  .muted {
    color: #64748b;
    font-size: 0.9rem;
  }
  .import {
    margin-top: 1.5rem;
    background: #f1f5f9;
    border-radius: 0.5rem;
    padding: 0.8rem;
  }
  .import h2 {
    margin: 0 0 0.5rem;
    font-size: 0.95rem;
  }
  .compare label {
    display: flex;
    flex-direction: column;
    font-size: 0.8rem;
  }
</style>
