<script lang="ts">
  import { goto } from '$app/navigation';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';

  let password = $state('');
  let error = $state('');

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    const res = await api('/api/auth/setup', {
      method: 'POST',
      body: JSON.stringify({ password })
    });
    if (res.status === 204) {
      await goto('/');
    } else if (res.status === 422) {
      error = $_('auth.error_too_short');
    } else {
      error = $_('auth.error_invalid');
    }
  }
</script>

<div class="card">
  <h1>{$_('auth.setup_title')}</h1>
  <p>{$_('auth.setup_hint')}</p>
  <form onsubmit={submit}>
    <label>
      {$_('auth.password')}
      <input type="password" bind:value={password} autocomplete="new-password" required />
    </label>
    {#if error}<p class="error">{error}</p>{/if}
    <button type="submit">{$_('auth.save')}</button>
  </form>
</div>

<style>
  .card {
    max-width: 20rem;
    margin: 15vh auto 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  input {
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
  }
  .error {
    color: #dc2626;
    margin: 0;
  }
</style>
