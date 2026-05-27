<script lang="ts">
  import { onMount } from 'svelte';
  import { uiStore } from '$lib/stores/ui.svelte';
  import { configStore } from '$lib/stores/config.svelte';
  import ProviderCard from './ProviderCard.svelte';
  import EmbeddingConfig from './EmbeddingConfig.svelte';
  import ApiKeyGuides from './ApiKeyGuides.svelte';

  type Tab = 'providers' | 'embedding' | 'about';
  let activeTab = $state<Tab>('providers');

  const PROVIDERS = ['ollama', 'openai', 'gemini', 'azure_openai'];

  onMount(() => {
    configStore.load();
  });

  // Reload config every time settings panel is opened.
  $effect(() => {
    if (uiStore.showSettings) {
      void configStore.load();
    }
  });

  // Auto-refresh Ollama status every 30s while panel is open
  $effect(() => {
    if (!uiStore.showSettings) return;
    const interval = setInterval(() => configStore.refreshProviders(), 30_000);
    return () => clearInterval(interval);
  });

  // Lazy-load backend version when About tab is selected
  $effect(() => {
    if (activeTab === 'about' && configStore.backendVersion === null) {
      configStore.fetchBackendVersion();
    }
  });

  function close() {
    uiStore.showSettings = false;
  }
</script>

{#if uiStore.showSettings}
  <div
    class="backdrop"
    role="presentation"
    onclick={close}
  ></div>

  <aside class="panel">
    <header class="panel-header">
      <span class="panel-title">⚙ Settings</span>
      <button class="close-btn" onclick={close} aria-label="Close settings">✕</button>
    </header>

    <!-- Tab bar -->
    <div class="tab-bar" role="tablist">
      {#each (['providers', 'embedding', 'about'] as Tab[]) as tab}
        <button
          class="tab"
          class:active={activeTab === tab}
          role="tab"
          aria-selected={activeTab === tab}
          onclick={() => (activeTab = tab)}
        >
          {tab === 'providers' ? 'LLM Providers' : tab === 'embedding' ? 'Embedding' : 'About'}
        </button>
      {/each}
    </div>

    <div class="panel-body">
      <!-- LLM Providers tab -->
      {#if activeTab === 'providers'}
        <div class="providers-list">
          {#each PROVIDERS as providerName}
            {#if configStore.config?.providers[providerName]}
              <ProviderCard
                name={providerName}
                config={configStore.config.providers[providerName]}
              />
            {/if}
          {/each}

          {#if !configStore.config}
            <p class="loading-hint">Loading config…</p>
            {#if configStore.loadError}
              <p class="load-error">{configStore.loadError}</p>
            {/if}
            <button class="retry-load" onclick={() => configStore.load()}>Retry</button>
          {/if}
        </div>

        <!-- Default Provider selector -->
        {#if configStore.config}
          <div class="default-provider-row">
            <label class="field-label" for="default-provider">Default Provider</label>
            <select
              id="default-provider"
              class="select"
              value={configStore.config.default_provider}
              onchange={(e) => configStore.setDefaultProvider((e.target as HTMLSelectElement).value)}
            >
              {#each PROVIDERS as p}
                <option value={p}>{p}</option>
              {/each}
            </select>
          </div>
        {/if}

        <ApiKeyGuides />

      <!-- Embedding tab -->
      {:else if activeTab === 'embedding'}
        <EmbeddingConfig />

      <!-- About tab -->
      {:else}
        <div class="about">
          <div class="about-logo">⚡</div>
          <h2 class="about-name">Hermes</h2>
          <p class="about-version">Version 0.1.0</p>
          {#if configStore.backendVersion}
            <p class="about-version">Backend {configStore.backendVersion}</p>
          {/if}
          <p class="about-desc">
            Local AI knowledge assistant — ask questions about your documents
            using on-device or cloud LLMs.
          </p>
          <a
            class="github-link"
            href="https://github.com/VladkoTatko/ProjectHermes"
            target="_blank"
            rel="noopener noreferrer"
          >View on GitHub ↗</a>
          <p class="about-license">Licensed under Apache 2.0</p>
        </div>
      {/if}

      {#if configStore.saveError}
        <div class="save-error" role="alert">⚠ {configStore.saveError}</div>
      {/if}
    </div>
  </aside>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 10;
  }

  .panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 480px;
    max-width: 100vw;
    height: 100vh;
    background: var(--bg-secondary);
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    z-index: 11;
    animation: slide-in 0.2s ease-out;
  }

  @keyframes slide-in {
    from { transform: translateX(100%); }
    to   { transform: translateX(0); }
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .panel-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .close-btn {
    font-size: 14px;
    color: var(--text-muted);
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    transition: color 0.15s, background 0.15s;
  }
  .close-btn:hover { color: var(--text-primary); background: var(--bg-primary); }

  .tab-bar {
    display: flex;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .tab {
    flex: 1;
    padding: 10px;
    font-size: 13px;
    color: var(--text-muted);
    border-bottom: 2px solid transparent;
    transition: color 0.15s, border-color 0.15s;
    text-align: center;
  }
  .tab:hover { color: var(--text-primary); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

  .panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .providers-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .loading-hint {
    font-size: 13px;
    color: var(--text-muted);
    text-align: center;
    padding: 16px 0 4px;
  }

  .load-error {
    font-size: 12px;
    color: var(--error);
    background: rgba(244, 67, 54, 0.08);
    border: 1px solid rgba(244, 67, 54, 0.3);
    border-radius: var(--radius-md);
    padding: 8px 10px;
    line-height: 1.4;
    margin: 0;
  }

  .retry-load {
    align-self: center;
    font-size: 12px;
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    transition: border-color 0.15s, color 0.15s;
  }

  .retry-load:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .default-provider-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .field-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .select {
    flex: 1;
    background: var(--bg-chat);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 6px 10px;
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s;
    appearance: auto;
  }
  .select:focus { border-color: var(--accent); }

  /* About tab */
  .about {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 24px 0;
    text-align: center;
  }

  .about-logo { font-size: 48px; }

  .about-name {
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
  }

  .about-version {
    font-size: 12px;
    color: var(--text-muted);
    margin: 0;
  }

  .about-desc {
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.6;
    max-width: 320px;
    margin: 4px 0;
  }

  .github-link {
    font-size: 13px;
    color: var(--accent);
    text-decoration: none;
  }
  .github-link:hover { text-decoration: underline; }

  .about-license {
    font-size: 11px;
    color: var(--text-muted);
    margin: 0;
  }

  .save-error {
    padding: 8px 12px;
    background: rgba(244, 67, 54, 0.1);
    border: 1px solid var(--error);
    border-radius: var(--radius-md);
    font-size: 12px;
    color: var(--error);
  }
</style>
