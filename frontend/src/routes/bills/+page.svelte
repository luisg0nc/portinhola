<script lang="ts">
  import { onMount } from 'svelte';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { formatCents } from '$lib/money';

  type BillItem = {
    id: number;
    doc_number: string;
    issue_date: string;
    period_start: string | null;
    period_end: string | null;
    total_cents: number;
    parse_status: string;
    utilities: string[];
    supplier_name: string | null;
  };

  let bills = $state<BillItem[]>([]);
  let filter = $state<string>('');
  let loaded = $state(false);

  const utilityIcons: Record<string, string> = { electricity: '⚡', gas: '🔥', water: '💧' };

  async function load() {
    const url = filter ? `/api/bills?utility=${filter}` : '/api/bills';
    const res = await api(url);
    if (res.ok) bills = await res.json();
    loaded = true;
  }

  onMount(load);

  function setFilter(value: string) {
    filter = value;
    load();
  }
</script>

<header>
  <h1>{$_('nav.bills')}</h1>
  <div class="actions">
    <a class="button" href="/bills/upload">{$_('bills.upload')}</a>
    <a class="button secondary" href="/bills/new">{$_('bills.manual_entry')}</a>
  </div>
</header>

<div class="filters">
  {#each ['', 'electricity', 'gas', 'water'] as value}
    <button class:active={filter === value} onclick={() => setFilter(value)}>
      {value ? utilityIcons[value] : $_('bills.all')}
    </button>
  {/each}
</div>

{#if loaded && bills.length === 0}
  <p>{$_('bills.no_bills')}</p>
{:else}
  <ul class="bill-list">
    {#each bills as bill}
      <li>
        <a href={`/bills/${bill.id}`}>
          <div class="row1">
            <span class="supplier">{bill.supplier_name ?? bill.doc_number}</span>
            <span class="total">{formatCents(bill.total_cents, $locale ?? 'pt')}</span>
          </div>
          <div class="row2">
            <span>{bill.utilities.map((u) => utilityIcons[u] ?? '').join(' ')} {bill.issue_date}</span>
            <span class={`badge ${bill.parse_status}`}>{$_(`bills.status_${bill.parse_status}`)}</span>
          </div>
        </a>
      </li>
    {/each}
  </ul>
{/if}

<style>
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
  }
  .button {
    background: #0f172a;
    color: white;
    padding: 0.5rem 0.9rem;
    border-radius: 0.4rem;
    text-decoration: none;
    font-size: 0.9rem;
  }
  .button.secondary {
    background: #475569;
  }
  .filters {
    display: flex;
    gap: 0.4rem;
    margin: 1rem 0;
  }
  .filters button {
    border: 1px solid #cbd5e1;
    background: white;
    border-radius: 999px;
    padding: 0.3rem 0.8rem;
    cursor: pointer;
  }
  .filters button.active {
    background: #0f172a;
    color: white;
    border-color: #0f172a;
  }
  .bill-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .bill-list a {
    display: block;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    padding: 0.7rem 0.9rem;
    text-decoration: none;
    color: inherit;
  }
  .row1 {
    display: flex;
    justify-content: space-between;
    font-weight: 600;
  }
  .row2 {
    display: flex;
    justify-content: space-between;
    color: #64748b;
    font-size: 0.85rem;
    margin-top: 0.2rem;
  }
  .badge {
    border-radius: 999px;
    padding: 0 0.5rem;
    font-size: 0.75rem;
    align-self: center;
  }
  .badge.parsed {
    background: #dcfce7;
    color: #166534;
  }
  .badge.partial {
    background: #fef9c3;
    color: #854d0e;
  }
  .badge.manual {
    background: #e2e8f0;
    color: #334155;
  }
</style>
