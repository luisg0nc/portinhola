<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';

  type Contract = {
    id: number;
    supplier_name: string;
    end_date: string | null;
    reading_day_start: number | null;
    reading_day_end: number | null;
    submit_url: string;
    submit_phone: string;
    submit_reference: string;
  };
  type Sp = {
    id: number;
    utility: string;
    identifier: string;
    name: string;
    contracts: Contract[];
  };
  type ReadingOut = {
    id: number;
    register: string;
    value: number;
    taken_at: string;
    submission_status: string;
  };

  let supplyPoints = $state<Sp[]>([]);
  let latestBySp = $state<Record<number, Record<string, ReadingOut>>>({});

  const icons: Record<string, string> = { electricity: '⚡', gas: '🔥', water: '💧' };

  onMount(async () => {
    const res = await api('/api/supply-points');
    if (!res.ok) return;
    supplyPoints = await res.json();
    for (const sp of supplyPoints) {
      const latestRes = await api(`/api/readings/latest?supply_point_id=${sp.id}`);
      if (latestRes.ok) latestBySp[sp.id] = await latestRes.json();
    }
  });

  function openContract(sp: Sp): Contract | undefined {
    return sp.contracts.find((c) => c.end_date === null);
  }

  async function markSubmitted(sp: Sp) {
    const readings = Object.values(latestBySp[sp.id] ?? {});
    for (const reading of readings) {
      if (reading.submission_status !== 'submitted_manual') {
        await api(`/api/readings/${reading.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ submission_status: 'submitted_manual' })
        });
      }
    }
    const latestRes = await api(`/api/readings/latest?supply_point_id=${sp.id}`);
    if (latestRes.ok) latestBySp[sp.id] = await latestRes.json();
  }
</script>

<h1>{$_('readings.title')}</h1>

{#each supplyPoints as sp}
  {@const contract = openContract(sp)}
  {@const latest = latestBySp[sp.id] ?? {}}
  <section class="card">
    <header>
      <strong>{icons[sp.utility]} {sp.name || sp.identifier}</strong>
      <a class="button" href={`/readings/new?sp=${sp.id}`}>{$_('readings.new_reading')}</a>
    </header>
    {#if Object.keys(latest).length === 0}
      <p class="muted">{$_('readings.no_readings')}</p>
    {:else}
      <ul class="registers">
        {#each Object.entries(latest) as [register, reading]}
          <li>
            <span class="reg">{register}</span>
            <span class="val">{reading.value}</span>
            <span class="muted">{reading.taken_at.slice(0, 10)}</span>
            <span class={`badge ${reading.submission_status}`}>
              {$_(`readings.status_${reading.submission_status}`)}
            </span>
          </li>
        {/each}
      </ul>
      {#if contract && Object.values(latest).some((r) => r.submission_status === 'needs_manual' || r.submission_status === 'not_submitted')}
        <div class="submit-info">
          <span>{$_('readings.submit_hint')}</span>
          <div class="row">
            {#if contract.submit_url}
              <a class="button small" href={contract.submit_url} target="_blank" rel="noreferrer">
                {$_('readings.open_portal')}
              </a>
            {/if}
            {#if contract.submit_phone}
              <a class="button small" href={`tel:${contract.submit_phone.replace(/\s/g, '')}`}>
                📞 {$_('readings.call_ivr')} {contract.submit_phone}
              </a>
            {/if}
            {#if contract.submit_reference}
              <span class="ref">{$_('readings.reference')}: <code>{contract.submit_reference}</code></span>
            {/if}
            <button class="small" onclick={() => markSubmitted(sp)}>
              {$_('readings.mark_submitted')}
            </button>
          </div>
        </div>
      {/if}
    {/if}
    <p class="muted window">
      {$_('readings.window')}:
      {#if contract?.reading_day_start && contract?.reading_day_end}
        {$_('readings.window_days')
          .replace('{start}', String(contract.reading_day_start))
          .replace('{end}', String(contract.reading_day_end))}
      {:else}
        {$_('readings.no_window')}
      {/if}
    </p>
  </section>
{/each}

<style>
  .card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.6rem;
    padding: 0.9rem;
    margin-bottom: 0.9rem;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }
  .button {
    background: #0f172a;
    color: white;
    padding: 0.45rem 0.8rem;
    border-radius: 0.4rem;
    text-decoration: none;
    font-size: 0.85rem;
    border: none;
    cursor: pointer;
  }
  .button.small,
  button.small {
    font-size: 0.8rem;
    padding: 0.35rem 0.6rem;
    background: #475569;
    color: white;
    border: none;
    border-radius: 0.35rem;
    cursor: pointer;
    text-decoration: none;
  }
  .registers {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .registers li {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .reg {
    font-weight: 600;
    min-width: 4rem;
  }
  .val {
    font-variant-numeric: tabular-nums;
    font-size: 1.05rem;
  }
  .muted {
    color: #94a3b8;
    font-size: 0.8rem;
  }
  .window {
    margin: 0.6rem 0 0;
  }
  .badge {
    border-radius: 999px;
    padding: 0 0.5rem;
    font-size: 0.72rem;
  }
  .badge.not_submitted {
    background: #fef9c3;
    color: #854d0e;
  }
  .badge.needs_manual {
    background: #fee2e2;
    color: #991b1b;
  }
  .badge.submitted_manual,
  .badge.submitted_auto {
    background: #dcfce7;
    color: #166534;
  }
  .submit-info {
    margin-top: 0.6rem;
    background: #f1f5f9;
    border-radius: 0.4rem;
    padding: 0.6rem;
    font-size: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .submit-info .row {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    align-items: center;
  }
  .ref code {
    background: white;
    padding: 0.1rem 0.4rem;
    border-radius: 0.25rem;
  }
</style>
