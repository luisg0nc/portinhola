<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { formatCents } from '$lib/money';
  import Card from '$lib/ui/Card.svelte';
  import Button from '$lib/ui/Button.svelte';
  import PageHeader from '$lib/ui/PageHeader.svelte';
  import UtilityBadge from '$lib/ui/UtilityBadge.svelte';
  import { ExternalLink, Trash2 } from '$lib/ui/icons';

  type Line = {
    id: number;
    contract_id: number | null;
    description: string;
    category: string;
    quantity: number | null;
    unit: string | null;
    unit_price: number | null;
    amount_cents: number;
    vat_rate: number | null;
  };
  type Detail = {
    id: number;
    issuer_nif: string;
    doc_number: string;
    atcud: string | null;
    issue_date: string;
    period_start: string | null;
    period_end: string | null;
    total_cents: number;
    parse_status: string;
    extractor: string | null;
    pdf_available: boolean;
    lines: Line[];
  };

  let bill = $state<Detail | null>(null);
  let contractUtility = $state<Record<number, string>>({});

  const categories = ['energy', 'power', 'fixed', 'tax', 'other'];
  const statusKind: Record<string, string> = {
    parsed: 'success',
    partial: 'warning',
    manual: 'neutral'
  };

  onMount(async () => {
    const res = await api(`/api/bills/${page.params.id}`);
    if (res.ok) bill = await res.json();
    const spRes = await api('/api/supply-points');
    if (spRes.ok) {
      const sps: { utility: string; contracts: { id: number }[] }[] = await spRes.json();
      const map: Record<number, string> = {};
      for (const sp of sps) for (const c of sp.contracts) map[c.id] = sp.utility;
      contractUtility = map;
    }
  });

  let groups = $derived.by(() => {
    if (!bill) return [];
    const byUtility = new Map<string, Line[]>();
    for (const line of bill.lines) {
      const utility =
        line.contract_id !== null ? (contractUtility[line.contract_id] ?? 'other') : 'other';
      byUtility.set(utility, [...(byUtility.get(utility) ?? []), line]);
    }
    return [...byUtility.entries()].map(([utility, lines]) => ({
      utility,
      lines,
      subtotals: categories
        .map((category) => ({
          category,
          cents: lines
            .filter((line) => line.category === category)
            .reduce((sum, line) => sum + line.amount_cents, 0)
        }))
        .filter((entry) => entry.cents !== 0),
      total: lines.reduce((sum, line) => sum + line.amount_cents, 0)
    }));
  });

  async function remove() {
    if (!bill) return;
    if (!window.confirm($_('bills.delete_confirm'))) return;
    const res = await api(`/api/bills/${bill.id}`, { method: 'DELETE' });
    if (res.status === 204) await goto('/bills');
  }
</script>

{#if bill}
  <PageHeader title={bill.doc_number}>
    {#snippet action()}
      <span class={`badge ${statusKind[bill!.parse_status] ?? 'neutral'}`}>
        {$_(`bills.status_${bill!.parse_status}`)}
      </span>
    {/snippet}
  </PageHeader>

  <Card>
    <div class="meta">
      <div><span class="muted">{$_('bills.issuer_nif')}</span> {bill.issuer_nif}</div>
      <div><span class="muted">{$_('bills.atcud')}</span> {bill.atcud ?? '—'}</div>
      <div><span class="muted">{$_('bills.date')}</span> {bill.issue_date}</div>
      {#if bill.period_start}
        <div>
          <span class="muted">{$_('bills.period')}</span>
          {bill.period_start} → {bill.period_end}
        </div>
      {/if}
    </div>
    <div class="total money">
      {$_('bills.total')}: {formatCents(bill.total_cents, $locale ?? 'pt')}
    </div>
  </Card>

  <div class="actions">
    {#if bill.pdf_available}
      <Button
        variant="secondary"
        href={`/api/bills/${bill.id}/pdf`}
        target="_blank"
        rel="noreferrer"
      >
        <ExternalLink size={16} />
        {$_('bills.open_pdf')}
      </Button>
    {/if}
    <Button variant="danger" onclick={remove}>
      <Trash2 size={16} />
      {$_('bills.delete')}
    </Button>
  </div>

  {#each groups as group}
    <Card>
      <div class="group-head">
        <UtilityBadge
          utility={group.utility}
          size="sm"
          label={$_(`dashboard.utility_${group.utility}`) === `dashboard.utility_${group.utility}`
            ? group.utility
            : $_(`dashboard.utility_${group.utility}`)}
        />
      </div>
      <div class="table-wrap">
        <table>
          <tbody>
            {#each group.lines as line}
              <tr>
                <td>{line.description}</td>
                <td class="muted">{$_(`bills.category_${line.category}`)}</td>
                <td class="amount money">{formatCents(line.amount_cents, $locale ?? 'pt')}</td>
              </tr>
            {/each}
          </tbody>
          <tfoot>
            {#each group.subtotals as subtotal}
              <tr class="subtotal">
                <td colspan="2">{$_(`bills.category_${subtotal.category}`)}</td>
                <td class="amount money">{formatCents(subtotal.cents, $locale ?? 'pt')}</td>
              </tr>
            {/each}
            <tr class="grand">
              <td colspan="2">{$_('bills.total')}</td>
              <td class="amount money">{formatCents(group.total, $locale ?? 'pt')}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Card>
  {/each}
{:else}
  <p class="muted">{$_('common.loading')}</p>
{/if}

<style>
  .meta {
    display: grid;
    gap: 0.3rem;
    font-size: 0.9rem;
  }
  .meta .muted {
    display: inline-block;
    min-width: 6rem;
  }
  .total {
    font-size: 1.2rem;
    font-weight: 800;
    margin-top: 0.6rem;
  }
  .actions {
    display: flex;
    gap: 0.6rem;
    margin-bottom: 1rem;
  }
  .group-head {
    margin-bottom: 0.5rem;
  }
  .table-wrap {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }
  td {
    border-bottom: 1px solid var(--line);
    padding: 0.45rem 0.3rem;
  }
  td.amount {
    text-align: right;
    white-space: nowrap;
  }
  tfoot .subtotal td {
    color: var(--ink-muted);
    font-weight: 600;
  }
  tfoot .grand td {
    font-weight: 800;
    border-top: 2px solid var(--ink);
    border-bottom: none;
  }
</style>
