<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';
  import Card from '$lib/ui/Card.svelte';
  import Button from '$lib/ui/Button.svelte';
  import PageHeader from '$lib/ui/PageHeader.svelte';
  import UtilityBadge from '$lib/ui/UtilityBadge.svelte';
  import EmptyState from '$lib/ui/EmptyState.svelte';
  import { Phone, ExternalLink, Check, Gauge } from '$lib/ui/icons';

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
  let loaded = $state(false);

  const badgeKind: Record<string, string> = {
    not_submitted: 'warning',
    needs_manual: 'danger',
    submitted_manual: 'success',
    submitted_auto: 'success'
  };

  onMount(async () => {
    const res = await api('/api/supply-points');
    if (!res.ok) return;
    supplyPoints = await res.json();
    for (const sp of supplyPoints) {
      const latestRes = await api(`/api/readings/latest?supply_point_id=${sp.id}`);
      if (latestRes.ok) latestBySp[sp.id] = await latestRes.json();
    }
    loaded = true;
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

<PageHeader title={$_('readings.title')} />

{#if loaded && supplyPoints.length === 0}
  <Card>
    <EmptyState icon={Gauge} message={$_('settings.no_supply_points')} />
  </Card>
{/if}

{#each supplyPoints as sp}
  {@const contract = openContract(sp)}
  {@const latest = latestBySp[sp.id] ?? {}}
  <Card>
    <header class="head">
      <UtilityBadge utility={sp.utility} label={sp.name || sp.identifier} />
      <Button size="sm" href={`/readings/new?sp=${sp.id}`}>{$_('readings.new_reading')}</Button>
    </header>
    {#if Object.keys(latest).length === 0}
      <p class="muted">{$_('readings.no_readings')}</p>
    {:else}
      <ul class="registers">
        {#each Object.entries(latest) as [register, reading]}
          <li>
            <span class="reg">{register}</span>
            <span class="val money">{reading.value}</span>
            <span class="muted">{reading.taken_at.slice(0, 10)}</span>
            <span class={`badge ${badgeKind[reading.submission_status] ?? 'neutral'}`}>
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
              <Button
                size="sm"
                variant="secondary"
                href={contract.submit_url}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={14} />
                {$_('readings.open_portal')}
              </Button>
            {/if}
            {#if contract.submit_phone}
              <Button
                size="sm"
                variant="secondary"
                href={`tel:${contract.submit_phone.replace(/\s/g, '')}`}
              >
                <Phone size={14} />
                {$_('readings.call_ivr')} {contract.submit_phone}
              </Button>
            {/if}
            {#if contract.submit_reference}
              <span class="ref muted">
                {$_('readings.reference')}: <code>{contract.submit_reference}</code>
              </span>
            {/if}
            <Button size="sm" onclick={() => markSubmitted(sp)}>
              <Check size={14} />
              {$_('readings.mark_submitted')}
            </Button>
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
  </Card>
{/each}

<style>
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.6rem;
  }
  .registers {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .registers li {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .reg {
    font-weight: 700;
    min-width: 4rem;
    font-size: 0.88rem;
  }
  .val {
    font-size: 1.05rem;
    font-weight: 700;
  }
  .window {
    margin: 0.6rem 0 0;
  }
  .submit-info {
    margin-top: 0.7rem;
    background: var(--surface-sunken);
    border-radius: var(--radius-control);
    padding: 0.7rem;
    font-size: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .submit-info .row {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    align-items: center;
  }
  .ref code {
    background: var(--surface);
    padding: 0.1rem 0.4rem;
    border-radius: 6px;
  }
</style>
