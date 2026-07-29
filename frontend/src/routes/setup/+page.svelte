<script lang="ts">
  import { goto } from '$app/navigation';
  import { _ } from 'svelte-i18n';
  import { api } from '$lib/api';
  import Card from '$lib/ui/Card.svelte';
  import Button from '$lib/ui/Button.svelte';

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

<div class="wrap">
  <span class="wordmark">Portinhola</span>
  <Card>
    <h1>{$_('auth.setup_title')}</h1>
    <p class="muted">{$_('auth.setup_hint')}</p>
    <form onsubmit={submit}>
      <label>
        {$_('auth.password')}
        <input type="password" bind:value={password} autocomplete="new-password" required />
      </label>
      {#if error}<p class="error">{error}</p>{/if}
      <Button type="submit" size="lg">{$_('auth.save')}</Button>
    </form>
  </Card>
</div>

<style>
  .wrap {
    max-width: 22rem;
    margin: 14vh auto 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .wordmark {
    text-align: center;
    font-size: 1.5rem;
    font-weight: 800;
    letter-spacing: -0.02em;
  }
  h1 {
    margin-bottom: 0.4rem;
  }
  form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-top: 0.8rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .error {
    color: var(--danger);
    margin: 0;
  }
</style>
