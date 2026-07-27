<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { _ } from 'svelte-i18n';

  let { onclose }: { onclose: (success: boolean) => void } = $props();

  let frameSrc = $state('');
  let pageW = $state(1024);
  let pageH = $state(768);
  let text = $state('');
  let error = $state('');
  let ws: WebSocket | null = null;
  let img: HTMLImageElement | undefined = $state();

  onMount(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/api/eredes/login`);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'frame') {
        frameSrc = `data:image/jpeg;base64,${msg.data}`;
        pageW = msg.w;
        pageH = msg.h;
      } else if (msg.type === 'success') {
        onclose(true);
      } else if (msg.type === 'error') {
        error = msg.message;
      }
    };
    ws.onerror = () => {
      error = 'websocket';
    };
  });

  onDestroy(() => ws?.close());

  function send(payload: object) {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  }

  function onImageClick(event: MouseEvent) {
    if (!img) return;
    const rect = img.getBoundingClientRect();
    const x = Math.round(((event.clientX - rect.left) / rect.width) * pageW);
    const y = Math.round(((event.clientY - rect.top) / rect.height) * pageH);
    send({ type: 'click', x, y });
  }

  function sendText(event: SubmitEvent) {
    event.preventDefault();
    if (text) {
      send({ type: 'type', text });
      text = '';
    }
  }
</script>

<div class="overlay">
  <div class="modal">
    <header>
      <h2>{$_('eredes.login_title')}</h2>
      <button class="close" onclick={() => onclose(false)}>✕</button>
    </header>
    <p class="hint">{$_('eredes.login_hint')}</p>
    {#if error}<p class="error">{$_('eredes.login_error')}: {error}</p>{/if}
    {#if frameSrc}
      <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions -->
      <img bind:this={img} src={frameSrc} alt="E-Redes" onclick={onImageClick} />
    {:else}
      <p>{$_('common.loading')}</p>
    {/if}
    <form onsubmit={sendText}>
      <input bind:value={text} placeholder={$_('eredes.type_placeholder')} />
      <button type="submit">{$_('eredes.send_text')}</button>
      <button type="button" onclick={() => send({ type: 'key', key: 'Enter' })}>
        {$_('eredes.press_enter')}
      </button>
    </form>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
    padding: 1rem;
  }
  .modal {
    background: white;
    border-radius: 0.6rem;
    padding: 1rem;
    max-width: 64rem;
    width: 100%;
    max-height: 95dvh;
    overflow: auto;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  header h2 {
    margin: 0;
    font-size: 1.1rem;
  }
  .close {
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
  }
  .hint {
    color: #64748b;
    font-size: 0.85rem;
  }
  img {
    width: 100%;
    border: 1px solid #e2e8f0;
    border-radius: 0.4rem;
    cursor: crosshair;
  }
  form {
    display: flex;
    gap: 0.4rem;
    margin-top: 0.6rem;
  }
  form input {
    flex: 1;
    padding: 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.35rem;
  }
  form button {
    padding: 0.5rem 0.8rem;
    border: none;
    border-radius: 0.35rem;
    background: #0f172a;
    color: white;
    cursor: pointer;
  }
  .error {
    color: #dc2626;
  }
</style>
