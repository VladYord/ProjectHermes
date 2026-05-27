<script lang="ts">
  import { configStore } from '$lib/stores/config.svelte';

  const EMBEDDING_PROVIDERS = ['hash', 'openai', 'ollama', 'azure_openai'];

  let currentProvider = $derived(configStore.config?.embedding_provider ?? 'hash');
  let modelInput = $state('');
  let showWarning = $state(false);

  $effect(() => {
    // Initialise modelInput from config on first load
    const cfg = configStore.config;
    if (!cfg) return;
    const p = currentProvider;
    if (p === 'ollama') {
      modelInput = (cfg.providers['ollama']?.embedding_model as string | undefined) ?? '';
    } else if (p === 'openai') {
      modelInput = 'text-embedding-3-small';
    } else if (p === 'azure_openai') {
      modelInput =
        (cfg.providers['azure_openai']?.embedding_deployment as string | undefined) ?? '';
    } else {
      modelInput = '';
    }
  });

  async function onProviderChange(e: Event) {
    const val = (e.target as HTMLSelectElement).value;
    showWarning = val !== currentProvider;
    await configStore.setEmbeddingProvider(val);
  }

  async function saveModel() {
    const val = modelInput.trim();
    if (!val) return;
    const cp = currentProvider;
    if (cp === 'ollama') {
      await configStore.saveProvider('ollama', { embedding_model: val });
    } else if (cp === 'azure_openai') {
      await configStore.saveProvider('azure_openai', { embedding_deployment: val });
    }
    // openai model is managed via ProviderCard
  }
</script>

<div class="embedding-config">
  {#if showWarning}
    <div class="warning-banner" role="alert">
      ⚠ Changing the embedding provider requires re-ingesting all documents.
      Your existing knowledge base will need to be rebuilt.
    </div>
  {/if}

  <div class="field">
    <label class="field-label" for="emb-provider">Embedding Provider</label>
    <select
      id="emb-provider"
      class="select"
      value={currentProvider}
      onchange={onProviderChange}
    >
      {#each EMBEDDING_PROVIDERS as p}
        <option value={p}>{p}</option>
      {/each}
    </select>
  </div>

  {#if currentProvider !== 'hash'}
    <div class="field">
      <label class="field-label" for="emb-model">
        {currentProvider === 'azure_openai' ? 'Embedding Deployment' : 'Embedding Model'}
      </label>
      <input
        id="emb-model"
        class="text-input"
        type="text"
        bind:value={modelInput}
        onblur={saveModel}
        placeholder="e.g. text-embedding-3-small"
      />
    </div>
  {:else}
    <p class="hash-note">
      Hash embeddings use a fast deterministic function — no API key required.
      Switch to OpenAI or Ollama for semantic (meaning-aware) search.
    </p>
  {/if}

  {#if configStore.isSaving}
    <p class="saving">Saving…</p>
  {/if}
  {#if configStore.saveError}
    <p class="error">{configStore.saveError}</p>
  {/if}
</div>

<style>
  .embedding-config {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .warning-banner {
    padding: 10px 12px;
    background: rgba(255, 152, 0, 0.1);
    border: 1px solid var(--warning);
    border-radius: var(--radius-md);
    font-size: 12px;
    color: var(--warning);
    line-height: 1.5;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .select, .text-input {
    background: var(--bg-primary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 8px 12px;
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s;
    width: 100%;
  }
  .select:focus, .text-input:focus { border-color: var(--accent); }
  .select { appearance: auto; }

  .hash-note {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .saving { font-size: 12px; color: var(--text-muted); }
  .error  { font-size: 12px; color: var(--error); }
</style>
