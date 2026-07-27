<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';

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

<h1>{$_('bills.manual_entry')}</h1>

<form onsubmit={submit}>
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
      {$_('bills.period')} —
      <input type="date" bind:value={periodStart} />
    </label>
    <label>
      &nbsp;
      <input type="date" bind:value={periodEnd} />
    </label>
  </div>

  <h2>{$_('bills.lines')}</h2>
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
      <button type="button" class="remove" onclick={() => removeLine(index)}>✕</button>
    </div>
  {/each}
  <button type="button" class="secondary" onclick={addLine}>{$_('bills.add_line')}</button>

  {#if error}<p class="error">{error}</p>{/if}
  <div class="buttons">
    <button type="submit">{$_('bills.confirm')}</button>
    <a href="/bills">{$_('bills.cancel')}</a>
  </div>
</form>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 0.7rem;
    max-width: 40rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    font-size: 0.9rem;
  }
  input,
  select {
    padding: 0.45rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.35rem;
    font-size: 0.9rem;
    background: white;
  }
  .line {
    display: flex;
    gap: 0.4rem;
    margin-bottom: 0.4rem;
    flex-wrap: wrap;
  }
  .line .desc {
    flex: 2 1 10rem;
  }
  .line .num {
    width: 5rem;
  }
  .remove {
    background: none;
    border: none;
    color: #dc2626;
    cursor: pointer;
    font-size: 1rem;
  }
  .secondary {
    background: #475569;
    color: white;
    border: none;
    border-radius: 0.4rem;
    padding: 0.5rem 0.9rem;
    cursor: pointer;
    margin-top: 0.4rem;
  }
  .buttons {
    margin-top: 1.2rem;
    display: flex;
    gap: 1rem;
    align-items: center;
  }
  .buttons button {
    padding: 0.7rem 1.2rem;
    border: none;
    border-radius: 0.4rem;
    background: #0f172a;
    color: white;
    font-size: 1rem;
    cursor: pointer;
  }
  .error {
    color: #dc2626;
  }
</style>
