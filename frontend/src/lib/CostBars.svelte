<script lang="ts">
  import { _, locale } from 'svelte-i18n';
  import { formatCents } from '$lib/money';

  type UtilityCosts = Record<string, number> & { total: number };
  type MonthEntry = { month: string; by_utility: Record<string, UtilityCosts> };

  let { months }: { months: MonthEntry[] } = $props();

  const colors: Record<string, string> = {
    electricity: '#f59e0b',
    gas: '#ef4444',
    water: '#0ea5e9',
    unknown: '#94a3b8'
  };

  let maxTotal = $derived(
    Math.max(
      1,
      ...months.map((m) =>
        Object.values(m.by_utility).reduce((sum, u) => sum + Math.max(0, u.total), 0)
      )
    )
  );

  function monthTotal(entry: MonthEntry): number {
    return Object.values(entry.by_utility).reduce((sum, u) => sum + u.total, 0);
  }
</script>

<div class="chart">
  {#each months as entry}
    <div class="col" title={`${entry.month}: ${formatCents(monthTotal(entry), $locale ?? 'pt')}`}>
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
    </div>
  {/each}
</div>
<div class="legend">
  {#each Object.entries(colors) as [utility, color]}
    <span><i style={`background:${color}`}></i>{$_(`dashboard.utility_${utility}`)}</span>
  {/each}
</div>

<style>
  .chart {
    display: flex;
    align-items: flex-end;
    gap: 0.35rem;
    height: 10rem;
    padding: 0.5rem 0;
  }
  .col {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
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
    border-radius: 2px 2px 0 0;
  }
  .label {
    font-size: 0.65rem;
    color: #64748b;
    margin-top: 0.2rem;
  }
  .legend {
    display: flex;
    gap: 0.9rem;
    font-size: 0.75rem;
    color: #475569;
    flex-wrap: wrap;
  }
  .legend i {
    display: inline-block;
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 2px;
    margin-right: 0.3rem;
  }
</style>
