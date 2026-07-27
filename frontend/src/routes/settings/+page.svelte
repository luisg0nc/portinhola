<script lang="ts">
  import { goto } from '$app/navigation';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';
  import { setLocale, type Locale } from '$lib/i18n';
  import { onMount } from 'svelte';

  let language = $state<Locale>('pt');
  let currentPassword = $state('');
  let newPassword = $state('');
  let passwordMessage = $state('');
  let languageMessage = $state('');

  onMount(async () => {
    const res = await api('/api/settings');
    if (res.ok) {
      language = (await res.json()).language;
    }
  });

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
</style>
