<script lang="ts">
  import { configStore } from '$lib/stores/config.svelte';

  const status = $derived(configStore.providers.find((p) => p.name === 'ollama'));
  const reachable = $derived(status?.reachable ?? null);
</script>

<div class="ollama-status">
  {#if reachable === true}
    <span class="dot green">●</span>
    <span class="label">Running</span>
    {#if status?.latency_ms != null}
      <span class="latency">{status.latency_ms}ms</span>
    {/if}
  {:else if reachable === false}
    <span class="dot red">●</span>
    <span class="label">Not running</span>
    <a
      href="https://ollama.com/download"
      target="_blank"
      rel="noopener noreferrer"
      class="setup-link"
    >Setup Guide ↗</a>
  {:else}
    <span class="dot yellow">●</span>
    <span class="label">Checking…</span>
  {/if}
</div>

<style>
  .ollama-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
  }

  .dot { font-size: 10px; }
  .green { color: var(--success); }
  .red   { color: var(--error); }
  .yellow { color: var(--warning); }

  .label { color: var(--text-muted); }

  .latency {
    color: var(--text-muted);
    font-size: 11px;
  }

  .setup-link {
    color: var(--accent);
    font-size: 11px;
    text-decoration: none;
  }
  .setup-link:hover { text-decoration: underline; }
</style>
