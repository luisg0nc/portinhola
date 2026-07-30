<script lang="ts">
  import { _, locale } from 'svelte-i18n';
  import { formatCents } from '$lib/money';

  type UtilityCosts = Record<string, number> & { total: number };
  type MonthEntry = { month: string; by_utility: Record<string, UtilityCosts> };

  let {
    months,
    selected = null,
    onselect
  }: {
    months: MonthEntry[];
    selected?: string | null;
    onselect?: (month: string) => void;
  } = $props();

  const colors: Record<string, string> = {
    electricity: 'var(--chart-electricity)',
    gas: 'var(--chart-gas)',
    water: 'var(--chart-water)',
    unknown: 'var(--chart-neutral)'
  };

  function monthTotal(entry: MonthEntry): number {
    return Object.values(entry.by_utility).reduce((sum, u) => sum + u.total, 0);
  }

  let maxTotal = $derived(
    Math.max(
      1,
      ...months.map((m) =>
        Object.values(m.by_utility).reduce((sum, u) => sum + Math.max(0, u.total), 0)
      )
    )
  );

  // Average over complete months only — the current month is still filling.
  let average = $derived.by(() => {
    const now = new Date().toISOString().slice(0, 7);
    const complete = months.filter((m) => m.month !== now);
    const pool = complete.length > 0 ? complete : months;
    return pool.reduce((sum, m) => sum + monthTotal(m), 0) / Math.max(1, pool.length);
  });
</script>

<div class="chart">
  {#if average > 0}
    <!-- bar area = chart height minus top padding (0.5rem) and the
         label row + bottom padding (~1.45rem) -->
    <div
      class="avg-line"
      style={`bottom: calc(1.45rem + (100% - 1.95rem) * ${(average / maxTotal).toFixed(4)})`}
    >
      <span class="avg-label">
        {$_('dashboard.avg_monthly')}: {formatCents(Math.round(average), $locale ?? 'pt')}
      </span>
    </div>
  {/if}
  {#each months as entry}
    <button
      class="col"
      class:selected={selected === entry.month}
      title={`${entry.month}: ${formatCents(monthTotal(entry), $locale ?? 'pt')}`}
      onclick={() => onselect?.(entry.month)}
    >
      <div class="bar">
        {#each Object.entries(entry.by_utility) as [utility, costs]}
          {#if costs.total > 0}
            <div
              class="segment"
              style={`height: ${(costs.total / maxTotal) * 100}%; background: ${colors[utility] ?? colors.unknown}`}
            ></div>
          {/if}
        {/each}
      </div>
      <span class="label">{entry.month.slice(5)}</span>
    </button>
  {/each}
</div>
<div class="legend">
  {#each Object.entries(colors) as [utility, color]}
    <span><i style={`background:${color}`}></i>{$_(`dashboard.utility_${utility}`)}</span>
  {/each}
</div>

<style>
  .chart {
    position: relative;
    display: flex;
    align-items: flex-end;
    gap: 0.25rem;
    height: 11rem;
    padding: 0.5rem 0;
  }
  .avg-line {
    position: absolute;
    left: 0;
    right: 0;
    border-top: 2px dashed var(--ink-muted);
    opacity: 0.55;
    pointer-events: none;
    z-index: 1;
  }
  .avg-label {
    position: absolute;
    right: 0;
    top: -1.15rem;
    font-size: 0.68rem;
    color: var(--ink-muted);
    background: var(--surface);
    padding: 0 0.25rem;
    border-radius: 4px;
  }
  .col {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
    min-width: 0;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    border-radius: 6px;
  }
  .col.selected {
    background: var(--accent-tint);
  }
  .bar {
    flex: 1;
    width: 100%;
    max-width: 2rem;
    display: flex;
    flex-direction: column-reverse;
    justify-content: flex-start;
  }
  .segment {
    width: 100%;
    border-radius: 3px 3px 0 0;
  }
  .label {
    font-size: 0.62rem;
    color: var(--ink-muted);
    margin-top: 0.2rem;
  }
  .legend {
    display: flex;
    gap: 0.9rem;
    font-size: 0.75rem;
    color: var(--ink-muted);
    flex-wrap: wrap;
  }
  .legend i {
    display: inline-block;
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 3px;
    margin-right: 0.3rem;
  }
</style>
