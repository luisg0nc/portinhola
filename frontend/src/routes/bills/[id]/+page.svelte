<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { formatCents } from '$lib/money';

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

  const icons: Record<string, string> = { electricity: '⚡', gas: '🔥', water: '💧', other: '📄' };

  async function remove() {
    if (!bill) return;
    if (!window.confirm($_('bills.delete_confirm'))) return;
    const res = await api(`/api/bills/${bill.id}`, { method: 'DELETE' });
    if (res.status === 204) await goto('/bills');
  }
</script>

{#if bill}
  <header>
    <h1>{bill.doc_number}</h1>
    <span class={`badge ${bill.parse_status}`}>{$_(`bills.status_${bill.parse_status}`)}</span>
  </header>

  <section class="meta">
    <div><strong>{$_('bills.issuer_nif')}:</strong> {bill.issuer_nif}</div>
    <div><strong>{$_('bills.atcud')}:</strong> {bill.atcud ?? '—'}</div>
    <div><strong>{$_('bills.date')}:</strong> {bill.issue_date}</div>
    {#if bill.period_start}
      <div><strong>{$_('bills.period')}:</strong> {bill.period_start} → {bill.period_end}</div>
    {/if}
    <div class="total">
      <strong>{$_('bills.total')}:</strong>
      {formatCents(bill.total_cents, $locale ?? 'pt')}
    </div>
  </section>

  <div class="actions">
    {#if bill.pdf_available}
      <a class="button" href={`/api/bills/${bill.id}/pdf`} target="_blank" rel="noreferrer">
        {$_('bills.open_pdf')}
      </a>
    {/if}
    <button class="danger" onclick={remove}>{$_('bills.delete')}</button>
  </div>

  {#each groups as group}
    <section class="group">
      <h2>{icons[group.utility]} {group.utility}</h2>
      <div class="table-wrap">
        <table>
          <tbody>
            {#each group.lines as line}
              <tr>
                <td>{line.description}</td>
                <td>{$_(`bills.category_${line.category}`)}</td>
                <td class="amount">{formatCents(line.amount_cents, $locale ?? 'pt')}</td>
              </tr>
            {/each}
          </tbody>
          <tfoot>
            {#each group.subtotals as subtotal}
              <tr class="subtotal">
                <td colspan="2">{$_(`bills.category_${subtotal.category}`)}</td>
                <td class="amount">{formatCents(subtotal.cents, $locale ?? 'pt')}</td>
              </tr>
            {/each}
            <tr class="grand">
              <td colspan="2">{$_('bills.total')}</td>
              <td class="amount">{formatCents(group.total, $locale ?? 'pt')}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  {/each}
{:else}
  <p>{$_('common.loading')}</p>
{/if}

<style>
  header {
    display: flex;
    align-items: center;
    gap: 0.7rem;
  }
  .meta {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    padding: 0.8rem;
    display: grid;
    gap: 0.3rem;
    margin-bottom: 1rem;
  }
  .meta .total {
    font-size: 1.1rem;
  }
  .actions {
    display: flex;
    gap: 0.7rem;
    margin-bottom: 1.2rem;
  }
  .button {
    background: #0f172a;
    color: white;
    padding: 0.5rem 0.9rem;
    border-radius: 0.4rem;
    text-decoration: none;
    font-size: 0.9rem;
  }
  .danger {
    background: #dc2626;
    color: white;
    border: none;
    border-radius: 0.4rem;
    padding: 0.5rem 0.9rem;
    cursor: pointer;
    font-size: 0.9rem;
  }
  .group h2 {
    font-size: 1.05rem;
  }
  .table-wrap {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    background: white;
  }
  td {
    border-bottom: 1px solid #e2e8f0;
    padding: 0.4rem;
  }
  td.amount {
    text-align: right;
    white-space: nowrap;
  }
  tfoot .subtotal td {
    color: #475569;
    font-weight: 600;
  }
  tfoot .grand td {
    font-weight: 700;
    border-top: 2px solid #0f172a;
  }
  .badge {
    border-radius: 999px;
    padding: 0.1rem 0.6rem;
    font-size: 0.75rem;
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
