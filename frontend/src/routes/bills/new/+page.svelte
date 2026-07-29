<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';
  import Card from '$lib/ui/Card.svelte';
  import Button from '$lib/ui/Button.svelte';
  import PageHeader from '$lib/ui/PageHeader.svelte';
  import { X } from '$lib/ui/icons';

  type ContractOption = { id: number; label: string };

  let issuerNif = $state('');
  let docNumber = $state('');
  let issueDate = $state('');
  let periodStart = $state('');
  let periodEnd = $state('');
  let totalEuros = $state('');
  let error = $state('');
  let contractOptions = $state<ContractOption[]>([]);
  let lines = $state<
    {
      description: string;
      category: string;
      amount_euros: string;
      vat_rate: string;
      contract_id: number | null;
    }[]
  >([]);

  const categories = ['energy', 'power', 'fixed', 'tax', 'other'];

  onMount(async () => {
    const res = await api('/api/supply-points');
    if (res.ok) {
      const sps: {
        identifier: string;
        contracts: { id: number; supplier_name: string; end_date: string | null }[];
      }[] = await res.json();
      contractOptions = sps.flatMap((sp) =>
        sp.contracts
          .filter((c) => c.end_date === null)
          .map((c) => ({ id: c.id, label: `${c.supplier_name} · ${sp.identifier}` }))
      );
    }
    addLine();
  });

  function addLine() {
    lines = [
      ...lines,
      { description: '', category: 'energy', amount_euros: '', vat_rate: '', contract_id: null }
    ];
  }

  function removeLine(index: number) {
    lines = lines.filter((_, i) => i !== index);
  }

  function euros_to_cents(value: string): number {
    return Math.round(parseFloat(value.replace(',', '.')) * 100) || 0;
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    const res = await api('/api/bills/confirm', {
      method: 'POST',
      body: JSON.stringify({
        upload_token: null,
        bill: {
          issuer_nif: issuerNif,
          doc_number: docNumber,
          issue_date: issueDate,
          period_start: periodStart || null,
          period_end: periodEnd || null,
          total_cents: euros_to_cents(totalEuros),
          parse_status: 'manual'
        },
        lines: lines
          .filter((line) => line.description)
          .map((line) => ({
            description: line.description,
            category: line.category,
            amount_cents: euros_to_cents(line.amount_euros),
            vat_rate: line.vat_rate ? parseInt(line.vat_rate) : null,
            contract_id: line.contract_id
          })),
        new_supply_points: []
      })
    });
    if (res.status === 201) {
      const { id } = await res.json();
      await goto(`/bills/${id}`);
    } else if (res.status === 409) {
      error = $_('bills.duplicate_warning');
    } else {
      error = $_('bills.upload_failed');
    }
  }
</script>

<PageHeader title={$_('bills.manual_entry')} />

<form onsubmit={submit}>
  <Card>
    <div class="grid">
      <label>
        {$_('bills.issuer_nif')}
        <input bind:value={issuerNif} required />
      </label>
      <label>
        {$_('bills.doc_number')}
        <input bind:value={docNumber} required />
      </label>
      <label>
        {$_('bills.date')}
        <input type="date" bind:value={issueDate} required />
      </label>
      <label>
        {$_('bills.total')} (€)
        <input inputmode="decimal" bind:value={totalEuros} required />
      </label>
      <label>
        {$_('bills.period')}
        <input type="date" bind:value={periodStart} />
      </label>
      <label>
        &nbsp;
        <input type="date" bind:value={periodEnd} />
      </label>
    </div>
  </Card>

  <Card>
    <h3>{$_('bills.lines')}</h3>
    {#each lines as line, index}
      <div class="line">
        <input class="desc" placeholder={$_('bills.description')} bind:value={line.description} />
        <select bind:value={line.category}>
          {#each categories as category}
            <option value={category}>{$_(`bills.category_${category}`)}</option>
          {/each}
        </select>
        <input class="num" inputmode="decimal" placeholder="€" bind:value={line.amount_euros} />
        <input class="num" inputmode="numeric" placeholder="%" bind:value={line.vat_rate} />
        <select bind:value={line.contract_id}>
          <option value={null}>{$_('bills.unassigned')}</option>
          {#each contractOptions as option}
            <option value={option.id}>{option.label}</option>
          {/each}
        </select>
        <button
          type="button"
          class="remove"
          onclick={() => removeLine(index)}
          aria-label={$_('bills.cancel')}
        >
          <X size={16} />
        </button>
      </div>
    {/each}
    <Button variant="secondary" size="sm" onclick={addLine}>{$_('bills.add_line')}</Button>
  </Card>

  {#if error}<p class="error">{error}</p>{/if}
  <div class="buttons">
    <Button type="submit">{$_('bills.confirm')}</Button>
    <Button variant="secondary" href="/bills">{$_('bills.cancel')}</Button>
  </div>
</form>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 0.7rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.85rem;
  }
  .line {
    display: flex;
    gap: 0.4rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
    align-items: center;
  }
  .line .desc {
    flex: 2 1 10rem;
  }
  .line .num {
    width: 5.5rem;
  }
  .remove {
    background: none;
    border: none;
    color: var(--danger);
    cursor: pointer;
    display: flex;
    padding: 0.4rem;
  }
  .buttons {
    display: flex;
    gap: 0.6rem;
    align-items: center;
  }
  .error {
    color: var(--danger);
  }
</style>
