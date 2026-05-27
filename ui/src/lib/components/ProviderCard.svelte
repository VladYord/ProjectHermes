<script lang="ts">
  import { untrack } from 'svelte';
  import { configStore } from '$lib/stores/config.svelte';
  import OllamaStatus from './OllamaStatus.svelte';
  import type { ProviderConfig } from '$lib/api/config';

  interface Props {
    name: string;
    config: ProviderConfig;
  }

  let { name, config }: Props = $props();

  // ── Display helpers ──────────────────────────────────────────

  const DISPLAY_NAMES: Record<string, string> = {
    openai: 'OpenAI',
    gemini: 'Google Gemini',
    ollama: 'Ollama (local)',
    azure_openai: 'Azure OpenAI',
  };

  const OPENAI_MODELS = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o3', 'o4-mini'];
  const GEMINI_MODELS = ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash'];

  const hasModelDropdown = $derived(name === 'openai' || name === 'gemini');
  const hasApiKey = $derived(name !== 'ollama');
  const hasUrl = $derived(name === 'ollama' || name === 'azure_openai');

  // ── Local state ──────────────────────────────────────────────

  let apiKeyInput = $state('');
  let showKey = $state(false);
  // Initialise editable fields once from props (not reactive — user owns the input)
  let modelInput = $state(untrack(() => config.model ?? config.deployment ?? ''));
  let urlInput = $state(untrack(() => config.base_url ?? ''));

  let testing = $state(false);
  let testResult = $state<{ ok: boolean; latency?: number } | null>(null);
  let saved = $state(false);

  // ── Status dot ───────────────────────────────────────────────

  const status = $derived(configStore.providers.find((p) => p.name === name));

  function statusDot(): string {
    if (name === 'ollama') {
      if (status?.reachable === true) return '🟢';
      if (status?.reachable === false) return '🔴';
      return '🟡';
    }
    if (status?.api_key_set) return '🟢';
    return '🔴';
  }

  function statusLabel(): string {
    if (name === 'ollama') {
      if (status?.reachable === true) return 'running';
      if (status?.reachable === false) return 'not running';
      return 'checking…';
    }
    return status?.api_key_set ? 'configured' : 'not configured';
  }

  // ── Actions ──────────────────────────────────────────────────

  async function saveApiKey() {
    const val = apiKeyInput.trim();
    if (!val) return;
    await configStore.saveProvider(name, { api_key: val });
    apiKeyInput = '';
    saved = true;
    setTimeout(() => (saved = false), 2000);
  }

  async function clearApiKey() {
    await configStore.saveProvider(name, { api_key: '' });
  }

  async function saveModel() {
    const val = modelInput.trim();
    if (!val) return;
    const patch = name === 'azure_openai' ? { deployment: val } : { model: val };
    await configStore.saveProvider(name, patch);
  }

  async function saveUrl() {
    const val = urlInput.trim();
    if (!val) return;
    await configStore.saveProvider(name, { base_url: val });
  }

  async function testConnection() {
    testing = true;
    testResult = null;
    await configStore.refreshProviders();
    const updated = configStore.providers.find((p) => p.name === name);
    if (updated) {
      testResult = {
        ok: name === 'ollama' ? (updated.reachable === true) : updated.api_key_set,
        latency: updated.latency_ms ?? undefined,
      };
    }
    testing = false;
  }
</script>

<div class="provider-card">
  <div class="card-header">
    <div class="provider-title">
      <span class="status-dot">{statusDot()}</span>
      <span class="provider-name">{DISPLAY_NAMES[name] ?? name}</span>
    </div>
    <span class="status-label" class:configured={statusLabel() === 'configured' || statusLabel() === 'running'}>
      {statusLabel()}
    </span>
  </div>

  <div class="card-body">
    <!-- API Key field (not for Ollama) -->
    {#if hasApiKey}
      <div class="field">
        <label class="field-label" for="{name}-key">API Key</label>
        <div class="key-row">
          <input
            id="{name}-key"
            class="text-input"
            type={showKey ? 'text' : 'password'}
            bind:value={apiKeyInput}
            placeholder={status?.api_key_set ? '••••••••••••' : 'Enter API key…'}
            onblur={saveApiKey}
            autocomplete="off"
          />
          <button
            class="icon-btn"
            onclick={() => (showKey = !showKey)}
            title={showKey ? 'Hide' : 'Show'}
            aria-label={showKey ? 'Hide API key' : 'Show API key'}
          >{showKey ? '🙈' : '👁'}</button>
          {#if status?.api_key_set}
            <button class="clear-btn" onclick={clearApiKey} title="Clear API key">✕</button>
          {/if}
        </div>
        {#if saved}<span class="saved-badge">✓ Saved</span>{/if}
      </div>
    {/if}

    <!-- URL field (Ollama + Azure OpenAI) -->
    {#if hasUrl}
      <div class="field">
        <label class="field-label" for="{name}-url">
          {name === 'azure_openai' ? 'Endpoint URL' : 'Ollama URL'}
        </label>
        <input
          id="{name}-url"
          class="text-input"
          type="url"
          bind:value={urlInput}
          placeholder="http://localhost:11434"
          onblur={saveUrl}
        />
      </div>
    {/if}

    <!-- Model field -->
    <div class="field">
      <label class="field-label" for="{name}-model">
        {name === 'azure_openai' ? 'Deployment' : 'Model'}
      </label>
      {#if hasModelDropdown}
        <select
          id="{name}-model"
          class="select"
          bind:value={modelInput}
          onchange={saveModel}
        >
          {#each (name === 'openai' ? OPENAI_MODELS : GEMINI_MODELS) as m}
            <option value={m}>{m}</option>
          {/each}
        </select>
      {:else}
        <input
          id="{name}-model"
          class="text-input"
          type="text"
          bind:value={modelInput}
          placeholder={name === 'ollama' ? 'e.g. llama3.1' : 'deployment-name'}
          onblur={saveModel}
        />
      {/if}
    </div>

    <!-- Ollama live status row -->
    {#if name === 'ollama'}
      <OllamaStatus />
    {/if}

    <!-- Test Connection -->
    <div class="actions-row">
      <button
        class="test-btn"
        onclick={testConnection}
        disabled={testing}
      >
        {#if testing}
          <span class="spinner">⟳</span> Testing…
        {:else}
          Test Connection
        {/if}
      </button>

      {#if testResult !== null}
        <span class="test-result" class:ok={testResult.ok} class:fail={!testResult.ok}>
          {testResult.ok ? '✓ OK' : '✕ Failed'}
          {#if testResult.latency != null}({testResult.latency}ms){/if}
        </span>
      {/if}
    </div>
  </div>
</div>

<style>
  .provider-card {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
  }

  .provider-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .status-dot { font-size: 12px; }

  .provider-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .status-label {
    font-size: 11px;
    color: var(--error);
    font-weight: 500;
  }
  .status-label.configured { color: var(--success); }

  .card-body {
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .field-label {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .key-row {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .key-row .text-input { flex: 1; }

  .text-input, .select {
    background: var(--bg-chat);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 7px 10px;
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s;
    width: 100%;
  }
  .text-input:focus, .select:focus { border-color: var(--accent); }
  .select { appearance: auto; }

  .icon-btn {
    flex-shrink: 0;
    font-size: 15px;
    padding: 4px 6px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    transition: color 0.15s;
  }
  .icon-btn:hover { color: var(--text-primary); }

  .clear-btn {
    flex-shrink: 0;
    font-size: 11px;
    padding: 4px 7px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    border: 1px solid var(--border);
    transition: color 0.15s;
  }
  .clear-btn:hover { color: var(--error); border-color: var(--error); }

  .saved-badge {
    font-size: 11px;
    color: var(--success);
  }

  .actions-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-top: 2px;
  }

  .test-btn {
    font-size: 12px;
    padding: 5px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    transition: border-color 0.15s, color 0.15s;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .test-btn:not(:disabled):hover { border-color: var(--accent); color: var(--accent); }
  .test-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .spinner {
    display: inline-block;
    animation: spin 1s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .test-result {
    font-size: 12px;
    font-weight: 500;
  }
  .test-result.ok   { color: var(--success); }
  .test-result.fail { color: var(--error); }
</style>
