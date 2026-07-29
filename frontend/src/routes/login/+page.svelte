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
    const res = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password })
    });
    if (res.status === 204) {
      await goto('/');
    } else if (res.status === 429) {
      error = $_('auth.error_rate_limited');
    } else {
      error = $_('auth.error_invalid');
    }
  }
</script>

<div class="wrap">
  <span class="wordmark">Portinhola</span>
  <Card>
    <h1>{$_('auth.login_title')}</h1>
    <form onsubmit={submit}>
      <label>
        {$_('auth.password')}
        <input type="password" bind:value={password} autocomplete="current-password" required />
      </label>
      {#if error}<p class="error">{error}</p>{/if}
      <Button type="submit" size="lg">{$_('auth.submit')}</Button>
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
    margin-bottom: 1rem;
  }
  form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
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
