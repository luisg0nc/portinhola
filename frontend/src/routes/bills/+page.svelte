<script lang="ts">
  import { onMount } from 'svelte';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import Card from '$lib/ui/Card.svelte';
  import Button from '$lib/ui/Button.svelte';
  import PageHeader from '$lib/ui/PageHeader.svelte';
  import EmptyState from '$lib/ui/EmptyState.svelte';
  import { formatCents } from '$lib/money';
  import { Upload, Pencil, ReceiptText } from '$lib/ui/icons';

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
  const statusKind: Record<string, string> = {
    parsed: 'success',
    partial: 'warning',
    manual: 'neutral'
  };

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

<PageHeader title={$_('nav.bills')}>
  {#snippet action()}
    <Button href="/bills/upload">
      <Upload size={16} />
      {$_('bills.upload')}
    </Button>
    <Button variant="secondary" href="/bills/new">
      <Pencil size={16} />
      {$_('bills.manual_entry')}
    </Button>
  {/snippet}
</PageHeader>

<div class="chip-row filters">
  {#each ['', 'electricity', 'gas', 'water'] as value}
    <button class="chip" class:active={filter === value} onclick={() => setFilter(value)}>
      {value ? `${utilityIcons[value]} ${$_(`dashboard.utility_${value}`)}` : $_('bills.all')}
    </button>
  {/each}
</div>

{#if loaded && bills.length === 0}
  <Card>
    <EmptyState icon={ReceiptText} message={$_('bills.no_bills')}>
      <Button href="/bills/upload">{$_('bills.upload')}</Button>
    </EmptyState>
  </Card>
{:else}
  <ul class="bill-list">
    {#each bills as bill}
      <li>
        <Card href={`/bills/${bill.id}`}>
          <div class="row1">
            <span class="supplier">{bill.supplier_name ?? bill.doc_number}</span>
            <span class="total money">{formatCents(bill.total_cents, $locale ?? 'pt')}</span>
          </div>
          <div class="row2">
            <span class="muted">
              {bill.utilities.map((u) => utilityIcons[u] ?? '').join(' ')}
              {bill.issue_date}
            </span>
            <span class={`badge ${statusKind[bill.parse_status] ?? 'neutral'}`}>
              {$_(`bills.status_${bill.parse_status}`)}
            </span>
          </div>
        </Card>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .filters {
    margin: 0 0 1rem;
  }
  .bill-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  .bill-list :global(.card) {
    margin-bottom: 0.6rem;
    padding: 0.8rem 1rem;
  }
  .row1 {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    font-weight: 700;
  }
  .row2 {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }
</style>
