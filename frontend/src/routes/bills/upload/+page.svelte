<script lang="ts">
  import { goto } from '$app/navigation';
  import { _, locale } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { formatCents } from '$lib/money';
  import Card from '$lib/ui/Card.svelte';
  import Button from '$lib/ui/Button.svelte';
  import PageHeader from '$lib/ui/PageHeader.svelte';
  import StatusBanner from '$lib/ui/StatusBanner.svelte';
  import { Upload } from '$lib/ui/icons';

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
  let dragging = $state(false);
  let draft = $state<Draft | null>(null);
  let lines = $state<ParsedLine[]>([]);
  let newSupplies = $state<
    { supply: ParsedSupply; name: string; supplier_name: string; start_date: string }[]
  >([]);
  let contractByUtility = $state<Record<string, number | null>>({});
  let existingOptions = $state<Record<string, ContractOption[]>>({});
  let submitting = $state(false);
  let fileInput = $state<HTMLInputElement | null>(null);

  const categories = ['energy', 'power', 'fixed', 'tax', 'other'];

  async function handleFile(file: File | undefined) {
    error = '';
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

  function onFile(event: Event) {
    const input = event.target as HTMLInputElement;
    handleFile(input.files?.[0]);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    dragging = false;
    handleFile(event.dataTransfer?.files?.[0]);
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

<PageHeader title={$_('bills.upload')} />

<div class="steps" aria-hidden="true">
  <span class="step" class:done={phase === 'review'} class:active={phase === 'pick'}>
    1 · {$_('bills.step_pick')}
  </span>
  <span class="step" class:active={phase === 'review'}>2 · {$_('bills.step_review')}</span>
</div>

{#if phase === 'pick'}
  <div
    class="dropzone"
    class:dragging
    role="button"
    tabindex="0"
    ondragover={(e) => {
      e.preventDefault();
      dragging = true;
    }}
    ondragleave={() => (dragging = false)}
    ondrop={onDrop}
    onclick={() => fileInput?.click()}
    onkeydown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') fileInput?.click();
    }}
  >
    <div class="disc"><Upload size={26} strokeWidth={1.8} /></div>
    <p>{$_('bills.drop_hint')}</p>
    <input
      bind:this={fileInput}
      type="file"
      accept="application/pdf,.pdf"
      onchange={onFile}
      class="hidden-input"
    />
  </div>
  {#if error}<p class="error">{error}</p>{/if}
{:else if draft}
  {#if draft.duplicate_of !== null}
    <StatusBanner kind="warning"><p>{$_('bills.duplicate_warning')}</p></StatusBanner>
  {/if}
  {#if !draft.parsed}
    <StatusBanner kind="info"><p>{$_('bills.parse_failed_hint')}</p></StatusBanner>
  {/if}

  {#if draft.qr}
    <Card>
      <div class="qr-grid">
        <div><span class="muted">{$_('bills.issuer_nif')}</span> {draft.qr.issuer_nif}</div>
        <div><span class="muted">{$_('bills.doc_number')}</span> {draft.qr.doc_number}</div>
        <div><span class="muted">{$_('bills.atcud')}</span> {draft.qr.atcud ?? '—'}</div>
        <div><span class="muted">{$_('bills.date')}</span> {draft.qr.issue_date}</div>
      </div>
      <div class="qr-total money">
        {$_('bills.total')}: {formatCents(draft.qr.total_cents, $locale ?? 'pt')}
      </div>
    </Card>
  {/if}

  {#each newSupplies as entry}
    <Card tinted>
      <h3>
        {$_('bills.create_supply_point')} — {entry.supply.identifier} ({entry.supply.utility})
      </h3>
      <div class="form-grid">
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
      </div>
      {#if entry.supply.power_kva}
        <p class="muted">{$_('bills.power_kva')}: {entry.supply.power_kva} · {entry.supply.cycle}</p>
      {/if}
      {#if entry.supply.gas_tier}
        <p class="muted">{$_('bills.gas_tier')}: {entry.supply.gas_tier}</p>
      {/if}
    </Card>
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
              <option value={-(index + 1)}>
                {$_('bills.new_contract_for')} {entry.supply.identifier}
              </option>
            {/if}
          {/each}
        </select>
      </label>
    {/if}
  {/each}

  {#if lines.length > 0}
    <Card>
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
                <td class="amount money">{formatCents(line.amount_cents, $locale ?? 'pt')}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </Card>
  {/if}

  {#if error}<p class="error">{error}</p>{/if}
  <div class="action-bar">
    <Button onclick={confirm} disabled={submitting || !draft.qr}>{$_('bills.confirm')}</Button>
    <Button variant="secondary" href="/bills">{$_('bills.cancel')}</Button>
  </div>
{/if}

<style>
  .steps {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  .step {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--ink-muted);
    background: var(--surface-sunken);
    border-radius: var(--radius-pill);
    padding: 0.25rem 0.75rem;
  }
  .step.active {
    background: var(--accent-tint);
    color: var(--accent);
  }
  .step.done {
    background: var(--success-tint);
    color: var(--success);
  }
  .dropzone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 0.3rem;
    padding: 3rem 1.5rem;
    background: var(--surface);
    border: 2px dashed var(--line);
    border-radius: var(--radius-card);
    color: var(--ink-muted);
    cursor: pointer;
  }
  .dropzone.dragging {
    border-color: var(--accent);
    background: var(--accent-tint);
    color: var(--accent);
  }
  .dropzone .disc {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 3.5rem;
    height: 3.5rem;
    border-radius: 50%;
    background: var(--accent-tint);
    color: var(--accent);
    margin-bottom: 0.6rem;
  }
  .dropzone p {
    margin: 0;
    max-width: 20rem;
  }
  .hidden-input {
    display: none;
  }
  .qr-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 0.35rem;
    font-size: 0.9rem;
  }
  .qr-grid .muted {
    display: inline-block;
    min-width: 5.5rem;
  }
  .qr-total {
    font-size: 1.15rem;
    font-weight: 800;
    margin-top: 0.6rem;
  }
  .form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
    gap: 0.7rem;
  }
  .form-grid label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .assign {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    margin-bottom: 0.9rem;
    max-width: 24rem;
  }
  .table-wrap {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }
  th {
    text-align: left;
    color: var(--ink-muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  th,
  td {
    border-bottom: 1px solid var(--line);
    padding: 0.4rem 0.3rem;
  }
  td input,
  td select {
    min-height: 36px;
    padding: 0.3rem 0.5rem;
    font-size: 0.85rem;
  }
  td.amount {
    text-align: right;
    white-space: nowrap;
  }
  .action-bar {
    position: sticky;
    bottom: max(0.7rem, env(safe-area-inset-bottom));
    display: flex;
    gap: 0.6rem;
    background: var(--surface);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-raised);
    padding: 0.7rem;
    margin-top: 1rem;
    z-index: 20;
  }
  .error {
    color: var(--danger);
  }
</style>
