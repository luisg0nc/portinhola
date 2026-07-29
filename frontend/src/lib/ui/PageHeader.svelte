<script lang="ts">
  import type { Snippet } from 'svelte';

  let { title, action }: { title: string; action?: Snippet } = $props();
</script>

<header>
  <h1>{title}</h1>
  {#if action}
    <div class="action">{@render action()}</div>
  {/if}
</header>

<style>
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin: 0.25rem 0 1.1rem;
  }
  .action {
    display: flex;
    gap: 0.5rem;
  }
</style>
