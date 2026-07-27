<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';

  type Sp = { id: number; utility: string; identifier: string; name: string };

  const REGISTERS: Record<string, string[]> = {
    electricity: ['Vazio', 'Cheias', 'Ponta'],
    gas: ['Total'],
    water: ['Total']
  };

  let supplyPoints = $state<Sp[]>([]);
  let spId = $state<number | null>(null);
  let values = $state<Record<string, string>>({});
  let previous = $state<Record<string, number>>({});
  let error = $state('');
  let decreaseInfo = $state<{ register: string; previous: number } | null>(null);

  const icons: Record<string, string> = { electricity: '⚡', gas: '🔥', water: '💧' };

  let selected = $derived(supplyPoints.find((sp) => sp.id === spId) ?? null);
  let registers = $derived(selected ? REGISTERS[selected.utility] : []);

  onMount(async () => {
    const res = await api('/api/supply-points');
    if (res.ok) {
      supplyPoints = await res.json();
      const fromQuery = Number(page.url.searchParams.get('sp'));
      spId = supplyPoints.some((sp) => sp.id === fromQuery)
        ? fromQuery
        : (supplyPoints[0]?.id ?? null);
      await loadPrevious();
    }
  });

  async function loadPrevious() {
    if (spId === null) return;
    values = {};
    previous = {};
    const res = await api(`/api/readings/latest?supply_point_id=${spId}`);
    if (res.ok) {
      const latest = await res.json();
      for (const [register, reading] of Object.entries(latest) as [string, { value: number }][]) {
        previous[register] = reading.value;
      }
    }
  }

  async function save(allowDecrease = false) {
    if (spId === null) return;
    error = '';
    decreaseInfo = null;
    const numeric: Record<string, number> = {};
    for (const register of registers) {
      const raw = (values[register] ?? '').replace(',', '.');
      if (raw) numeric[register] = parseFloat(raw);
    }
    if (Object.keys(numeric).length === 0) return;
    const res = await api('/api/readings', {
      method: 'POST',
      body: JSON.stringify({
        supply_point_id: spId,
        values: numeric,
        allow_decrease: allowDecrease
      })
    });
    if (res.status === 201) {
      await goto('/readings');
    } else if (res.status === 422) {
      const detail = (await res.json()).detail;
      if (detail?.error === 'value_decreased') {
        decreaseInfo = { register: detail.register, previous: detail.previous };
      } else {
        error = JSON.stringify(detail);
      }
    } else {
      error = 'error';
    }
  }
</script>

<h1>{$_('readings.new_reading')}</h1>

{#if supplyPoints.length > 1}
  <select bind:value={spId} onchange={loadPrevious}>
    {#each supplyPoints as sp}
      <option value={sp.id}>{icons[sp.utility]} {sp.name || sp.identifier}</option>
    {/each}
  </select>
{/if}

{#if selected}
  <form
    onsubmit={(e) => {
      e.preventDefault();
      save();
    }}
  >
    {#each registers as register}
      <label>
        {register}
        <input
          inputmode="decimal"
          autocomplete="off"
          placeholder={previous[register] !== undefined ? String(previous[register]) : ''}
          bind:value={values[register]}
        />
        {#if previous[register] !== undefined}
          <span class="prev">{$_('readings.previous')}: {previous[register]}</span>
        {/if}
      </label>
    {/each}

    {#if decreaseInfo}
      <div class="warning">
        <p>
          {$_('readings.decrease_warning').replace('{previous}', String(decreaseInfo.previous))}
        </p>
        <div class="row">
          <button type="button" onclick={() => save(true)}>
            {$_('readings.confirm_decrease')}
          </button>
          <button type="button" class="secondary" onclick={() => (decreaseInfo = null)}>
            {$_('readings.cancel')}
          </button>
        </div>
      </div>
    {/if}
    {#if error}<p class="error">{error}</p>{/if}
    <button type="submit" class="save">{$_('readings.save')}</button>
  </form>
{/if}

<style>
  select {
    padding: 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.4rem;
    font-size: 1rem;
    margin-bottom: 1rem;
  }
  form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-width: 22rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-weight: 600;
  }
  input {
    padding: 0.9rem;
    font-size: 1.6rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.5rem;
    font-variant-numeric: tabular-nums;
  }
  .prev {
    font-weight: 400;
    color: #64748b;
    font-size: 0.8rem;
  }
  .save {
    padding: 1rem;
    font-size: 1.1rem;
    background: #0f172a;
    color: white;
    border: none;
    border-radius: 0.5rem;
    cursor: pointer;
  }
  .warning {
    background: #fef9c3;
    border: 1px solid #fde047;
    border-radius: 0.5rem;
    padding: 0.7rem;
  }
  .warning .row {
    display: flex;
    gap: 0.6rem;
  }
  .warning button {
    padding: 0.5rem 0.8rem;
    border: none;
    border-radius: 0.4rem;
    background: #0f172a;
    color: white;
    cursor: pointer;
  }
  .warning .secondary {
    background: #64748b;
  }
  .error {
    color: #dc2626;
  }
</style>
