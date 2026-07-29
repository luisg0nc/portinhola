<script lang="ts">
  import { goto } from '$app/navigation';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { setLocale, type Locale } from '$lib/i18n';
  import { onMount } from 'svelte';

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

  const utilityIcons: Record<string, string> = { electricity: '⚡', gas: '🔥', water: '💧' };

  async function loadSupplyPoints() {
    const res = await api('/api/supply-points');
    if (res.ok) supplyPoints = await res.json();
  }

  let appriseUrls = $state('');
  let syncTime = $state('07:00');
  let notifyMessage = $state('');
  let eredesConnected = $state(false);
  let eredesValidUntil = $state<string | null>(null);
  let eredesMessage = $state('');
  let curlText = $state('');
  let curlError = $state('');
  let curlSaved = $state(false);
  let guideSteps = $derived([
    $_('eredes.guide_step_1'),
    $_('eredes.guide_step_2'),
    $_('eredes.guide_step_3'),
    $_('eredes.guide_step_4'),
    $_('eredes.guide_step_5'),
    $_('eredes.guide_step_6')
  ]);

  async function loadEredes() {
    const res = await api('/api/eredes/status');
    if (res.ok) {
      const data = await res.json();
      eredesConnected = data.connected;
      eredesValidUntil = data.valid_until;
    }
  }

  onMount(async () => {
    const res = await api('/api/settings');
    if (res.ok) {
      const data = await res.json();
      language = data.language;
      appriseUrls = data.apprise_urls ?? '';
      syncTime = data.eredes_sync_time ?? '07:00';
    }
    await loadSupplyPoints();
    await loadEredes();
  });

  async function saveExtras() {
    await api('/api/settings', {
      method: 'PUT',
      body: JSON.stringify({ language, apprise_urls: appriseUrls, eredes_sync_time: syncTime })
    });
  }

  async function testNotification() {
    await saveExtras();
    const res = await api('/api/settings/test-notification', { method: 'POST' });
    const sent = res.ok && (await res.json()).sent;
    notifyMessage = sent ? $_('notifications.test_sent') : $_('notifications.test_failed');
  }

  async function syncNow() {
    const res = await api('/api/jobs/eredes_sync/run', { method: 'POST' });
    eredesMessage = res.status === 202 ? $_('eredes.sync_started') : '';
  }

  async function disconnectEredes() {
    await api('/api/eredes/disconnect', { method: 'POST' });
    await loadEredes();
  }

  async function saveCurl() {
    curlError = '';
    curlSaved = false;
    const res = await api('/api/eredes/import', {
      method: 'POST',
      body: JSON.stringify({ curl: curlText })
    });
    if (res.ok) {
      curlSaved = true;
      curlText = '';
      await loadEredes();
    } else {
      const detail = (await res.json()).detail;
      curlError = `eredes.err_${detail}`;
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

<h1>{$_('settings.title')}</h1>

<section>
  <label>
    {$_('settings.language')}
    <select value={language} onchange={changeLanguage}>
      <option value="pt">{$_('settings.language_pt')}</option>
      <option value="en">{$_('settings.language_en')}</option>
    </select>
  </label>
  {#if languageMessage}<p>{languageMessage}</p>{/if}
</section>

<section>
  <h2>{$_('auth.change_password')}</h2>
  <form onsubmit={changePassword}>
    <label>
      {$_('auth.current_password')}
      <input type="password" bind:value={currentPassword} autocomplete="current-password" required />
    </label>
    <label>
      {$_('auth.new_password')}
      <input type="password" bind:value={newPassword} autocomplete="new-password" required />
    </label>
    <button type="submit">{$_('auth.save')}</button>
  </form>
  {#if passwordMessage}<p>{passwordMessage}</p>{/if}
</section>

<section class="eredes">
  <h2>{$_('eredes.title')}</h2>
  <p>
    <strong>{eredesConnected ? $_('eredes.connected') : $_('eredes.not_connected')}</strong>
    {#if eredesValidUntil}
      <span class="muted">
        · {$_('eredes.valid_until').replace('{date}', eredesValidUntil.slice(0, 16))}
      </span>
    {/if}
  </p>

  <label>
    {$_('eredes.import_label')}
    <textarea bind:value={curlText} rows="4" placeholder="curl '...'"></textarea>
  </label>
  {#if curlError}<p class="error">{$_(curlError)}</p>{/if}
  {#if curlSaved}<p class="ok">{$_('eredes.saved')}</p>{/if}
  <div class="row">
    <button onclick={saveCurl}>{$_('eredes.save')}</button>
    {#if eredesConnected}
      <button onclick={syncNow}>{$_('eredes.sync_now')}</button>
      <button class="secondary" onclick={disconnectEredes}>{$_('eredes.disconnect')}</button>
    {/if}
  </div>
  {#if eredesMessage}<p>{eredesMessage}</p>{/if}

  <label>
    {$_('eredes.sync_time')}
    <input type="time" bind:value={syncTime} onchange={saveExtras} />
  </label>

  <details class="guide">
    <summary>{$_('eredes.guide_toggle')}</summary>
    <ol>
      {#each guideSteps as step}<li>{step}</li>{/each}
    </ol>
    <p class="muted">{$_('eredes.guide_security')}</p>
  </details>
</section>

<section class="notify">
  <h2>{$_('notifications.title')}</h2>
  <label>
    {$_('notifications.apprise_urls')}
    <textarea rows="3" bind:value={appriseUrls} onchange={saveExtras}></textarea>
  </label>
  <p class="muted">{$_('notifications.apprise_hint')}</p>
  <button onclick={testNotification}>{$_('notifications.test')}</button>
  {#if notifyMessage}<p>{notifyMessage}</p>{/if}
</section>

<section class="supply">
  <h2>{$_('settings.supply_points')}</h2>
  {#if supplyPoints.length === 0}
    <p>{$_('settings.no_supply_points')}</p>
  {/if}
  {#each supplyPoints as sp}
    <div class="sp-card">
      <div class="sp-head">
        <strong>{utilityIcons[sp.utility]} {sp.name || sp.identifier}</strong>
        <span class="muted">{sp.identifier}</span>
      </div>
      {#each sp.contracts as contract}
        {#if editingContract && editingContract.id === contract.id}
          <form class="contract-edit" onsubmit={saveContract}>
            <label>
              {$_('bills.supplier')}
              <input bind:value={editingContract.supplier_name} />
            </label>
            <label>
              {$_('bills.category_energy')}
              <input bind:value={editingContract.tariff_name} placeholder="Tarifa" />
            </label>
            {#if sp.utility === 'electricity'}
              <label>
                {$_('bills.power_kva')}
                <input type="number" step="0.05" bind:value={editingContract.power_kva} />
              </label>
              <label>
                {$_('bills.cycle')}
                <select bind:value={editingContract.cycle}>
                  <option value="simples">simples</option>
                  <option value="bi-horario">bi-horário</option>
                  <option value="tri-horario">tri-horário</option>
                </select>
              </label>
            {/if}
            {#if sp.utility === 'gas'}
              <label>
                {$_('bills.gas_tier')}
                <input type="number" bind:value={editingContract.gas_tier} />
              </label>
            {/if}
            <label>
              {$_('contract.reading_window')}
              <span class="range">
                <input type="number" min="1" max="31" bind:value={editingContract.reading_day_start} />
                –
                <input type="number" min="1" max="31" bind:value={editingContract.reading_day_end} />
              </span>
            </label>
            <label>
              {$_('contract.submit_url')}
              <input bind:value={editingContract.submit_url} placeholder="https://…" />
            </label>
            <label>
              {$_('contract.submit_phone')}
              <input bind:value={editingContract.submit_phone} placeholder="800 …" />
            </label>
            <label>
              {$_('contract.submit_reference')}
              <input bind:value={editingContract.submit_reference} />
            </label>
            <button type="submit">{$_('settings.save_contract')}</button>
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
    <label>
      {$_('settings.utility')}
      <select bind:value={newSp.utility}>
        <option value="electricity">⚡ {$_('dashboard.utility_electricity')}</option>
        <option value="gas">🔥 {$_('dashboard.utility_gas')}</option>
        <option value="water">💧 {$_('dashboard.utility_water')}</option>
      </select>
    </label>
    <label>
      {$_('bills.identifier')}
      <input bind:value={newSp.identifier} required placeholder="CPE / CUI / nº contador" />
    </label>
    <label>
      {$_('bills.name')}
      <input bind:value={newSp.name} placeholder="Casa" />
    </label>
    {#if spMessage}<p class="error">{spMessage}</p>{/if}
    <button type="submit">{$_('auth.save')}</button>
  </form>
</section>

<section>
  <button class="logout" onclick={logout}>{$_('auth.logout')}</button>
</section>

<style>
  section {
    margin-bottom: 2rem;
    max-width: 24rem;
  }
  form,
  label {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  input,
  select {
    padding: 0.6rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.4rem;
    font-size: 1rem;
  }
  button {
    padding: 0.7rem;
    border: none;
    border-radius: 0.4rem;
    background: #0f172a;
    color: white;
    font-size: 1rem;
    cursor: pointer;
    align-self: flex-start;
  }
  .logout {
    background: #dc2626;
  }
  .sp-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    padding: 0.7rem;
    margin-bottom: 0.7rem;
  }
  .sp-head {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.4rem;
  }
  .muted {
    color: #94a3b8;
    font-size: 0.8rem;
  }
  .contract-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    padding: 0.3rem 0;
    border-top: 1px solid #f1f5f9;
    gap: 0.5rem;
  }
  .contract-edit {
    border-top: 1px solid #f1f5f9;
    padding-top: 0.5rem;
  }
  .link {
    background: none;
    border: none;
    color: #2563eb;
    cursor: pointer;
    padding: 0;
    font-size: 0.85rem;
  }
  .sp-add {
    margin-top: 1rem;
    background: #f1f5f9;
    border-radius: 0.5rem;
    padding: 0.8rem;
  }
  .sp-add h3 {
    margin: 0 0 0.5rem;
    font-size: 0.95rem;
  }
  .error {
    color: #dc2626;
  }
  .supply {
    max-width: 34rem;
  }
  .range {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }
  .range input {
    width: 4.5rem;
  }
  .eredes .row {
    display: flex;
    gap: 0.6rem;
    margin-bottom: 0.6rem;
  }
  .secondary {
    background: #475569;
  }
  textarea {
    padding: 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.35rem;
    font-family: monospace;
    font-size: 0.85rem;
  }
</style>
