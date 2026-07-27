<script lang="ts">
  import { goto } from '$app/navigation';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { formatCents } from '$lib/money';

  type ParsedLine = {
    description: string;
    category: string;
    utility: string | null;
    period_start: string | null;
    period_end: string | null;
    quantity: number | null;
    unit: string | null;
    unit_price: number | null;
    amount_cents: number;
    vat_rate: number | null;
  };
  type ParsedSupply = {
    utility: string;
    identifier: string;
    tariff_name: string;
    power_kva: number | null;
    cycle: string | null;
    gas_tier: number | null;
  };
  type SupplyMatch = {
    identifier: string;
    supply_point_id: number | null;
    contract_id: number | null;
  };
  type Draft = {
    upload_token: string;
    qr: {
      issuer_nif: string;
      buyer_nif: string | null;
      doc_type: string;
      doc_number: string;
      atcud: string | null;
      issue_date: string;
      total_cents: number;
      vat_fields: Record<string, string>;
      raw: string;
    } | null;
    parsed: {
      supplier_name: string;
      period_start: string | null;
      period_end: string | null;
      supplies: ParsedSupply[];
      lines: ParsedLine[];
    } | null;
    extractor: string | null;
    supply_matches: SupplyMatch[];
    duplicate_of: number | null;
  };
  type ContractOption = { id: number; label: string };

  let phase = $state<'pick' | 'review'>('pick');
  let error = $state('');
  let draft = $state<Draft | null>(null);
  let lines = $state<ParsedLine[]>([]);
  // supplies to create: parsed supplies with no existing match, editable
  let newSupplies = $state<
    { supply: ParsedSupply; name: string; supplier_name: string; start_date: string }[]
  >([]);
  // utility -> contract ref: existing id (>0) or negative index into newSupplies, or null
  let contractByUtility = $state<Record<string, number | null>>({});
  let existingOptions = $state<Record<string, ContractOption[]>>({});
  let submitting = $state(false);

  const categories = ['energy', 'power', 'fixed', 'tax', 'other'];

  async function onFile(event: Event) {
    error = '';
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/api/bills/upload', { method: 'POST', body: form });
    if (!res.ok) {
      error = $_('bills.upload_failed');
      return;
    }
    draft = await res.json();
    await prepareReview();
    phase = 'review';
  }

  async function prepareReview() {
    if (!draft) return;
    lines = draft.parsed ? [...draft.parsed.lines] : [];
    newSupplies = [];
    contractByUtility = {};
    existingOptions = {};

    const res = await api('/api/supply-points');
    const supplyPoints: {
      id: number;
      utility: string;
      identifier: string;
      name: string;
      contracts: { id: number; supplier_name: string; end_date: string | null }[];
    }[] = res.ok ? await res.json() : [];

    for (const sp of supplyPoints) {
      const open = sp.contracts.filter((c) => c.end_date === null);
      existingOptions[sp.utility] = [
        ...(existingOptions[sp.utility] ?? []),
        ...open.map((c) => ({ id: c.id, label: `${c.supplier_name} · ${sp.identifier}` }))
      ];
    }

    if (draft.parsed) {
      for (const supply of draft.parsed.supplies) {
        const match = draft.supply_matches.find((m) => m.identifier === supply.identifier);
        if (match?.contract_id) {
          contractByUtility[supply.utility] = match.contract_id;
        } else {
          newSupplies.push({
            supply,
            name: '',
            supplier_name: draft.parsed.supplier_name,
            start_date: draft.parsed.period_start ?? draft.qr?.issue_date ?? ''
          });
          contractByUtility[supply.utility] = -newSupplies.length;
        }
      }
    }
  }

  async function confirm() {
    if (!draft || !draft.qr) return;
    submitting = true;
    error = '';
    const payload = {
      upload_token: draft.upload_token,
      bill: {
        issuer_nif: draft.qr.issuer_nif,
        customer_nif: draft.qr.buyer_nif,
        doc_type: draft.qr.doc_type,
        doc_number: draft.qr.doc_number,
        atcud: draft.qr.atcud,
        issue_date: draft.qr.issue_date,
        period_start: draft.parsed?.period_start ?? null,
        period_end: draft.parsed?.period_end ?? null,
        total_cents: draft.qr.total_cents,
        vat_fields: draft.qr.vat_fields,
        parse_status: draft.parsed ? 'parsed' : 'partial',
        extractor: draft.extractor,
        qr_raw: draft.qr.raw
      },
      lines: lines.map((line) => ({
        ...line,
        contract_id: line.utility ? (contractByUtility[line.utility] ?? null) : null
      })),
      new_supply_points: newSupplies.map((entry) => ({
        utility: entry.supply.utility,
        identifier: entry.supply.identifier,
        name: entry.name,
        contract: {
          supplier_name: entry.supplier_name,
          supplier_nif: draft!.qr!.issuer_nif,
          tariff_name: entry.supply.tariff_name,
          power_kva: entry.supply.power_kva,
          cycle: entry.supply.cycle,
          gas_tier: entry.supply.gas_tier,
          start_date: entry.start_date
        }
      }))
    };
    const res = await api('/api/bills/confirm', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    submitting = false;
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

<h1>{$_('bills.upload')}</h1>

{#if phase === 'pick'}
  <input type="file" accept="application/pdf,.pdf" onchange={onFile} />
  {#if error}<p class="error">{error}</p>{/if}
{:else if draft}
  <h2>{$_('bills.review_title')}</h2>

  {#if draft.duplicate_of !== null}
    <p class="warning">{$_('bills.duplicate_warning')}</p>
  {/if}
  {#if !draft.parsed}
    <p class="hint">{$_('bills.parse_failed_hint')}</p>
  {/if}

  {#if draft.qr}
    <section class="qr">
      <div><strong>{$_('bills.issuer_nif')}:</strong> {draft.qr.issuer_nif}</div>
      <div><strong>{$_('bills.doc_number')}:</strong> {draft.qr.doc_number}</div>
      <div><strong>{$_('bills.atcud')}:</strong> {draft.qr.atcud ?? '—'}</div>
      <div><strong>{$_('bills.date')}:</strong> {draft.qr.issue_date}</div>
      <div>
        <strong>{$_('bills.total')}:</strong>
        {formatCents(draft.qr.total_cents, $locale ?? 'pt')}
      </div>
    </section>
  {/if}

  {#each newSupplies as entry, index}
    <section class="card">
      <h3>{$_('bills.create_supply_point')} — {entry.supply.identifier} ({entry.supply.utility})</h3>
      <label>
        {$_('bills.name')}
        <input bind:value={entry.name} placeholder="Casa" />
      </label>
      <label>
        {$_('bills.supplier')}
        <input bind:value={entry.supplier_name} />
      </label>
      <label>
        {$_('bills.start_date')}
        <input type="date" bind:value={entry.start_date} />
      </label>
      {#if entry.supply.power_kva}
        <div>{$_('bills.power_kva')}: {entry.supply.power_kva} · {entry.supply.cycle}</div>
      {/if}
      {#if entry.supply.gas_tier}
        <div>{$_('bills.gas_tier')}: {entry.supply.gas_tier}</div>
      {/if}
    </section>
  {/each}

  {#each Object.keys(contractByUtility) as utility}
    {#if (existingOptions[utility] ?? []).length > 0}
      <label class="assign">
        {$_('bills.assign_contract')} {utility}
        <select bind:value={contractByUtility[utility]}>
          {#each existingOptions[utility] ?? [] as option}
            <option value={option.id}>{option.label}</option>
          {/each}
          {#each newSupplies as entry, index}
            {#if entry.supply.utility === utility}
              <option value={-(index + 1)}>{$_('bills.new_contract_for')} {entry.supply.identifier}</option>
            {/if}
          {/each}
        </select>
      </label>
    {/if}
  {/each}

  {#if lines.length > 0}
    <h3>{$_('bills.lines')} ({lines.length})</h3>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{$_('bills.description')}</th>
            <th>{$_('bills.category')}</th>
            <th>{$_('bills.vat')}</th>
            <th>{$_('bills.amount')}</th>
          </tr>
        </thead>
        <tbody>
          {#each lines as line}
            <tr>
              <td><input bind:value={line.description} /></td>
              <td>
                <select bind:value={line.category}>
                  {#each categories as category}
                    <option value={category}>{$_(`bills.category_${category}`)}</option>
                  {/each}
                </select>
              </td>
              <td>{line.vat_rate !== null ? `${line.vat_rate}%` : '—'}</td>
              <td class="amount">{formatCents(line.amount_cents, $locale ?? 'pt')}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if error}<p class="error">{error}</p>{/if}
  <div class="buttons">
    <button onclick={confirm} disabled={submitting || !draft.qr}>{$_('bills.confirm')}</button>
    <a href="/bills" class="cancel">{$_('bills.cancel')}</a>
  </div>
{/if}

<style>
  section.qr {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    padding: 0.8rem;
    display: grid;
    gap: 0.3rem;
    margin-bottom: 1rem;
  }
  .card {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 0.5rem;
    padding: 0.8rem;
    margin-bottom: 1rem;
    display: grid;
    gap: 0.5rem;
  }
  .card h3 {
    margin: 0;
    font-size: 1rem;
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
  .assign {
    margin-bottom: 0.8rem;
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
  th,
  td {
    border-bottom: 1px solid #e2e8f0;
    padding: 0.4rem;
    text-align: left;
  }
  td.amount {
    text-align: right;
    white-space: nowrap;
  }
  .buttons {
    margin-top: 1rem;
    display: flex;
    gap: 1rem;
    align-items: center;
  }
  button {
    padding: 0.7rem 1.2rem;
    border: none;
    border-radius: 0.4rem;
    background: #0f172a;
    color: white;
    font-size: 1rem;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.5;
  }
  .error {
    color: #dc2626;
  }
  .warning {
    background: #fef9c3;
    border: 1px solid #fde047;
    padding: 0.6rem;
    border-radius: 0.4rem;
  }
  .hint {
    color: #64748b;
  }
</style>
