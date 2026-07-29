<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';
  import Button from '$lib/ui/Button.svelte';
  import PageHeader from '$lib/ui/PageHeader.svelte';
  import UtilityBadge from '$lib/ui/UtilityBadge.svelte';
  import StatusBanner from '$lib/ui/StatusBanner.svelte';

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

  async function selectSp(id: number) {
    spId = id;
    await loadPrevious();
  }

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

<PageHeader title={$_('readings.new_reading')} />

{#if supplyPoints.length > 1}
  <div class="chip-row picker">
    {#each supplyPoints as sp}
      <button
        type="button"
        class="chip"
        class:active={spId === sp.id}
        onclick={() => selectSp(sp.id)}
      >
        <UtilityBadge utility={sp.utility} size="sm" />
        {sp.name || sp.identifier}
      </button>
    {/each}
  </div>
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
          <span class="prev muted">{$_('readings.previous')}: {previous[register]}</span>
        {/if}
      </label>
    {/each}

    {#if decreaseInfo}
      <StatusBanner kind="warning">
        <p>
          {$_('readings.decrease_warning').replace('{previous}', String(decreaseInfo.previous))}
        </p>
        <div class="banner-row">
          <Button size="sm" onclick={() => save(true)}>
            {$_('readings.confirm_decrease')}
          </Button>
          <Button size="sm" variant="secondary" onclick={() => (decreaseInfo = null)}>
            {$_('readings.cancel')}
          </Button>
        </div>
      </StatusBanner>
    {/if}
    {#if error}<p class="error">{error}</p>{/if}
    <Button type="submit" size="lg">{$_('readings.save')}</Button>
  </form>
{/if}

<style>
  .picker {
    margin-bottom: 1.1rem;
  }
  form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-width: 24rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-weight: 700;
  }
  input {
    padding: 0.9rem;
    font-size: 1.6rem;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }
  .prev {
    font-weight: 500;
  }
  .banner-row {
    display: flex;
    gap: 0.5rem;
  }
  .error {
    color: var(--danger);
  }
</style>
