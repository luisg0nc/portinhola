<script lang="ts">
  import { goto } from '$app/navigation';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { setLocale, type Locale } from '$lib/i18n';
  import { onDestroy, onMount } from 'svelte';
  import Card from '$lib/ui/Card.svelte';
  import StatusBanner from '$lib/ui/StatusBanner.svelte';
  import Button from '$lib/ui/Button.svelte';
  import PageHeader from '$lib/ui/PageHeader.svelte';
  import UtilityBadge from '$lib/ui/UtilityBadge.svelte';

  type Contract = {
    id: number;
    supplier_name: string;
    supplier_nif: string;
    tariff_name: string;
    power_kva: number | null;
    cycle: string | null;
    gas_tier: number | null;
    start_date: string;
    end_date: string | null;
    reading_day_start: number | null;
    reading_day_end: number | null;
    submit_url: string;
    submit_phone: string;
    submit_reference: string;
  };
  type SupplyPoint = {
    id: number;
    utility: string;
    identifier: string;
    name: string;
    contracts: Contract[];
  };

  let language = $state<Locale>('pt');
  let currentPassword = $state('');
  let newPassword = $state('');
  let passwordMessage = $state('');
  let languageMessage = $state('');
  let supplyPoints = $state<SupplyPoint[]>([]);
  let newSp = $state({ utility: 'electricity', identifier: '', name: '' });
  let spMessage = $state('');
  let editingContract = $state<Contract | null>(null);

  async function loadSupplyPoints() {
    const res = await api('/api/supply-points');
    if (res.ok) supplyPoints = await res.json();
  }

  type EredesJob = { status: string; message: string | null; finished_at: string | null };

  let appriseUrls = $state('');
  let notifyMessage = $state('');
  let eredesConnected = $state(false);
  let eredesNeedsSp = $state(false);
  let eredesLastSync = $state<string | null>(null);
  let eredesJob = $state<EredesJob | null>(null);
  let syncing = $state(false);
  let pollTimer: ReturnType<typeof setTimeout> | undefined;
  let tokenText = $state('');
  let tokenError = $state('');
  let tokenSaved = $state(false);
  let guideSteps = $derived([
    $_('eredes.guide_step_1'),
    $_('eredes.guide_step_2'),
    $_('eredes.guide_step_3'),
    $_('eredes.guide_step_4'),
    $_('eredes.guide_step_5')
  ]);

  async function loadEredes() {
    const res = await api('/api/eredes/status');
    if (res.ok) {
      const data = await res.json();
      eredesConnected = data.connected;
      eredesNeedsSp = data.needs_supply_point;
      eredesLastSync = data.last_sync;
      eredesJob = data.last_job;
    }
  }

  // The sync runs as a subprocess; poll until its job row finishes so the
  // user sees the real outcome, not just "started". `before` must be the
  // finished_at seen BEFORE the sync was triggered — fast jobs can finish
  // before the first poll.
  function watchSync(before: string | null) {
    syncing = true;
    clearTimeout(pollTimer);
    const startedAt = Date.now();
    const poll = async () => {
      await loadEredes();
      const done = eredesJob && eredesJob.finished_at !== before && eredesJob.status !== 'running';
      if (done || Date.now() - startedAt > 180000) {
        syncing = false;
        return;
      }
      pollTimer = setTimeout(poll, 2000);
    };
    pollTimer = setTimeout(poll, 1500);
  }

  onDestroy(() => clearTimeout(pollTimer));

  const knownFailures = ['no_supply_point', 'not_connected', 'session_expired', 'no_data'];

  function jobDetail(job: EredesJob): string {
    if (job.status === 'failed' && job.message && knownFailures.includes(job.message)) {
      return $_(`eredes.fail_${job.message}`);
    }
    return job.message ?? '';
  }

  onMount(async () => {
    const res = await api('/api/settings');
    if (res.ok) {
      const data = await res.json();
      language = data.language;
      appriseUrls = data.apprise_urls ?? '';
    }
    await loadSupplyPoints();
    await loadEredes();
  });

  async function saveExtras() {
    await api('/api/settings', {
      method: 'PUT',
      body: JSON.stringify({ language, apprise_urls: appriseUrls })
    });
  }

  async function testNotification() {
    await saveExtras();
    const res = await api('/api/settings/test-notification', { method: 'POST' });
    const sent = res.ok && (await res.json()).sent;
    notifyMessage = sent ? $_('notifications.test_sent') : $_('notifications.test_failed');
  }

  async function syncNow() {
    const before = eredesJob?.finished_at ?? null;
    const res = await api('/api/jobs/eredes_sync/run', { method: 'POST' });
    if (res.status === 202) watchSync(before);
  }

  async function disconnectEredes() {
    await api('/api/eredes/disconnect', { method: 'POST' });
    await loadEredes();
  }

  async function saveToken() {
    tokenError = '';
    tokenSaved = false;
    const before = eredesJob?.finished_at ?? null;
    const res = await api('/api/eredes/import', {
      method: 'POST',
      body: JSON.stringify({ token: tokenText })
    });
    if (res.ok) {
      tokenSaved = true;
      tokenText = '';
      watchSync(before);
    } else {
      const detail = (await res.json()).detail;
      tokenError = `eredes.err_${detail}`;
    }
  }

  async function addSupplyPoint(event: SubmitEvent) {
    event.preventDefault();
    spMessage = '';
    const res = await api('/api/supply-points', {
      method: 'POST',
      body: JSON.stringify(newSp)
    });
    if (res.status === 201) {
      newSp = { utility: 'electricity', identifier: '', name: '' };
      await loadSupplyPoints();
    } else {
      spMessage = res.status === 409 ? 'identifier_exists' : 'error';
    }
  }

  async function saveContract(event: SubmitEvent) {
    event.preventDefault();
    if (!editingContract) return;
    const { id, ...fields } = editingContract;
    const res = await api(`/api/supply-points/contracts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(fields)
    });
    if (res.ok) {
      editingContract = null;
      await loadSupplyPoints();
    }
  }

  async function changeLanguage(event: Event) {
    const next = (event.target as HTMLSelectElement).value as Locale;
    language = next;
    setLocale(next);
    const res = await api('/api/settings', {
      method: 'PUT',
      body: JSON.stringify({ language: next })
    });
    languageMessage = res.status === 204 ? $_('settings.saved') : '';
  }

  async function changePassword(event: SubmitEvent) {
    event.preventDefault();
    passwordMessage = '';
    const res = await api('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    });
    if (res.status === 204) {
      passwordMessage = $_('settings.saved');
      currentPassword = '';
      newPassword = '';
    } else if (res.status === 422) {
      passwordMessage = $_('auth.error_too_short');
    } else {
      passwordMessage = $_('auth.error_invalid');
    }
  }

  async function logout() {
    await api('/api/auth/logout', { method: 'POST' });
    await goto('/login');
  }
</script>

<PageHeader title={$_('settings.title')} />

<div class="sections">
  <Card>
    <h2>{$_('settings.language')}</h2>
    <label class="stack">
      <select value={language} onchange={changeLanguage}>
        <option value="pt">{$_('settings.language_pt')}</option>
        <option value="en">{$_('settings.language_en')}</option>
      </select>
    </label>
    {#if languageMessage}<p class="ok">{languageMessage}</p>{/if}
  </Card>

  <Card>
    <h2>{$_('eredes.title')}</h2>
    <p class="status">
      <span class={`badge ${eredesConnected ? 'success' : 'neutral'}`}>
        {eredesConnected ? $_('eredes.connected') : $_('eredes.not_connected')}
      </span>
      {#if eredesLastSync}
        <span class="muted">
          {$_('eredes.last_sync_label')}: {eredesLastSync.slice(0, 16).replace('T', ' ')}
        </span>
      {/if}
    </p>

    {#if eredesNeedsSp}
      <StatusBanner kind="warning"><p>{$_('eredes.needs_sp')}</p></StatusBanner>
    {/if}

    <label class="stack">
      {$_('eredes.import_label')}
      <textarea bind:value={tokenText} rows="3" placeholder="aat…"></textarea>
    </label>
    {#if tokenError}<p class="error">{$_(tokenError)}</p>{/if}
    {#if tokenSaved}<p class="ok">{$_('eredes.saved')}</p>{/if}
    <div class="row">
      <Button onclick={saveToken}>{$_('eredes.save')}</Button>
      {#if eredesConnected}
        <Button variant="secondary" onclick={syncNow} disabled={syncing}>
          {$_('eredes.sync_now')}
        </Button>
        <Button variant="danger" onclick={disconnectEredes}>{$_('eredes.disconnect')}</Button>
      {/if}
    </div>
    {#if syncing}
      <p class="muted">{$_('eredes.sync_running')}</p>
    {:else if eredesJob}
      {#if eredesJob.status === 'success'}
        <p class="ok">{$_('eredes.sync_ok').replace('{detail}', jobDetail(eredesJob))}</p>
      {:else if eredesJob.status === 'failed'}
        <p class="error">{$_('eredes.sync_failed').replace('{detail}', jobDetail(eredesJob))}</p>
      {/if}
    {/if}
    <p class="muted">{$_('eredes.token_note')}</p>

    <details class="guide">
      <summary>{$_('eredes.guide_toggle')}</summary>
      <ol>
        {#each guideSteps as step}<li>{step}</li>{/each}
      </ol>
      <p class="muted">{$_('eredes.guide_security')}</p>
    </details>
  </Card>

  <Card>
    <h2>{$_('settings.supply_points')}</h2>
    {#if supplyPoints.length === 0}
      <p class="muted">{$_('settings.no_supply_points')}</p>
    {/if}
    {#each supplyPoints as sp}
      <div class="sp-card">
        <div class="sp-head">
          <UtilityBadge utility={sp.utility} size="sm" label={sp.name || sp.identifier} />
          <span class="muted">{sp.identifier}</span>
        </div>
        {#each sp.contracts as contract}
          {#if editingContract && editingContract.id === contract.id}
            <form class="contract-edit" onsubmit={saveContract}>
              <label class="stack">
                {$_('bills.supplier')}
                <input bind:value={editingContract.supplier_name} />
              </label>
              <label class="stack">
                {$_('bills.category_energy')}
                <input bind:value={editingContract.tariff_name} placeholder="Tarifa" />
              </label>
              {#if sp.utility === 'electricity'}
                <label class="stack">
                  {$_('bills.power_kva')}
                  <input type="number" step="0.05" bind:value={editingContract.power_kva} />
                </label>
                <label class="stack">
                  {$_('bills.cycle')}
                  <select bind:value={editingContract.cycle}>
                    <option value="simples">simples</option>
                    <option value="bi-horario">bi-horário</option>
                    <option value="tri-horario">tri-horário</option>
                  </select>
                </label>
              {/if}
              {#if sp.utility === 'gas'}
                <label class="stack">
                  {$_('bills.gas_tier')}
                  <input type="number" bind:value={editingContract.gas_tier} />
                </label>
              {/if}
              <label class="stack">
                {$_('contract.reading_window')}
                <span class="range">
                  <input
                    type="number"
                    min="1"
                    max="31"
                    bind:value={editingContract.reading_day_start}
                  />
                  –
                  <input
                    type="number"
                    min="1"
                    max="31"
                    bind:value={editingContract.reading_day_end}
                  />
                </span>
              </label>
              <label class="stack">
                {$_('contract.submit_url')}
                <input bind:value={editingContract.submit_url} placeholder="https://…" />
              </label>
              <label class="stack">
                {$_('contract.submit_phone')}
                <input bind:value={editingContract.submit_phone} placeholder="800 …" />
              </label>
              <label class="stack">
                {$_('contract.submit_reference')}
                <input bind:value={editingContract.submit_reference} />
              </label>
              <Button type="submit">{$_('settings.save_contract')}</Button>
            </form>
          {:else}
            <div class="contract-row">
              <span>
                {contract.supplier_name}
                {#if contract.tariff_name}· {contract.tariff_name}{/if}
                {#if contract.power_kva}· {contract.power_kva} kVA ({contract.cycle}){/if}
                {#if contract.gas_tier}· {$_('bills.gas_tier')} {contract.gas_tier}{/if}
                <span class="muted">
                  {contract.start_date} → {contract.end_date ?? '…'}
                </span>
              </span>
              <button class="link" onclick={() => (editingContract = { ...contract })}>
                {$_('settings.edit')}
              </button>
            </div>
          {/if}
        {/each}
      </div>
    {/each}

    <form class="sp-add" onsubmit={addSupplyPoint}>
      <h3>{$_('settings.add_supply_point')}</h3>
      <label class="stack">
        {$_('settings.utility')}
        <select bind:value={newSp.utility}>
          <option value="electricity">⚡ {$_('dashboard.utility_electricity')}</option>
          <option value="gas">🔥 {$_('dashboard.utility_gas')}</option>
          <option value="water">💧 {$_('dashboard.utility_water')}</option>
        </select>
      </label>
      <label class="stack">
        {$_('bills.identifier')}
        <input bind:value={newSp.identifier} required placeholder="CPE / CUI / nº contador" />
      </label>
      <label class="stack">
        {$_('bills.name')}
        <input bind:value={newSp.name} placeholder="Casa" />
      </label>
      {#if spMessage}<p class="error">{spMessage}</p>{/if}
      <Button type="submit">{$_('auth.save')}</Button>
    </form>
  </Card>

  <Card>
    <h2>{$_('auth.change_password')}</h2>
    <form onsubmit={changePassword}>
      <label class="stack">
        {$_('auth.current_password')}
        <input
          type="password"
          bind:value={currentPassword}
          autocomplete="current-password"
          required
        />
      </label>
      <label class="stack">
        {$_('auth.new_password')}
        <input type="password" bind:value={newPassword} autocomplete="new-password" required />
      </label>
      <Button type="submit">{$_('auth.save')}</Button>
    </form>
    {#if passwordMessage}<p class="ok">{passwordMessage}</p>{/if}
  </Card>

  <Card>
    <h2>{$_('notifications.title')}</h2>
    <label class="stack">
      {$_('notifications.apprise_urls')}
      <textarea rows="3" bind:value={appriseUrls} onchange={saveExtras}></textarea>
    </label>
    <p class="muted">{$_('notifications.apprise_hint')}</p>
    <Button variant="secondary" onclick={testNotification}>{$_('notifications.test')}</Button>
    {#if notifyMessage}<p class="ok">{notifyMessage}</p>{/if}
  </Card>

  <Card>
    <Button variant="danger" onclick={logout}>{$_('auth.logout')}</Button>
  </Card>
</div>

<style>
  .sections {
    max-width: 34rem;
  }
  form {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    align-items: flex-start;
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    align-self: stretch;
  }
  .status {
    margin: 0 0 0.75rem;
  }
  .row {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin: 0.75rem 0;
  }
  .sp-card {
    border-top: 1px solid var(--line);
    padding: 0.7rem 0;
  }
  .sp-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.4rem;
  }
  .contract-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    padding: 0.3rem 0;
    gap: 0.5rem;
  }
  .contract-edit {
    padding-top: 0.5rem;
  }
  .link {
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    padding: 0;
    font-size: 0.85rem;
    font-family: var(--font);
    font-weight: 600;
  }
  .sp-add {
    margin-top: 1rem;
    background: var(--surface-sunken);
    border-radius: var(--radius-control);
    padding: 0.9rem;
  }
  .sp-add h3 {
    margin-bottom: 0.5rem;
  }
  .error {
    color: var(--danger);
  }
  .ok {
    color: var(--success);
    font-size: 0.85rem;
  }
  .range {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }
  .range input {
    width: 5rem;
  }
  .guide summary {
    cursor: pointer;
    font-weight: 600;
    font-size: 0.88rem;
  }
  .guide ol {
    padding-left: 1.2rem;
    font-size: 0.88rem;
  }
  textarea {
    font-family: monospace;
    font-size: 0.85rem;
  }
</style>
