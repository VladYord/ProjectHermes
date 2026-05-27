<script lang="ts">
  import { onMount } from 'svelte';
  import { uiStore } from '$lib/stores/ui.svelte';
  import { docStore } from '$lib/stores/documents.svelte';
  import DocumentCard from './DocumentCard.svelte';
  import UploadButton from './UploadButton.svelte';
  import IngestionProgress from './IngestionProgress.svelte';

  onMount(() => {
    docStore.refreshDocuments();
  });

  // If backend starts after initial app load, refresh when panel is opened.
  $effect(() => {
    if (uiStore.showDocManager) {
      void docStore.refreshDocuments();
    }
  });
</script>

{#if uiStore.showDocManager}
  <!-- Overlay backdrop -->
  <div
    class="backdrop"
    role="presentation"
    onclick={() => (uiStore.showDocManager = false)}
  ></div>

  <!-- Panel -->
  <aside class="panel">
    <header class="panel-header">
      <span class="panel-title">📄 Knowledge Base</span>
      <button
        class="close-btn"
        onclick={() => (uiStore.showDocManager = false)}
        title="Close"
        aria-label="Close document manager"
      >✕</button>
    </header>

    <div class="panel-body">
      <UploadButton />

      <p class="hint">
        Supported: PDF, TXT, Markdown, DOCX, code files, images (OCR)
      </p>

      <IngestionProgress />

      <div class="doc-list-header">
        <span class="doc-count">
          {docStore.documents.length}
          {docStore.documents.length === 1 ? 'document' : 'documents'} in knowledge base
        </span>
        <button
          class="refresh-btn"
          onclick={() => docStore.refreshDocuments()}
          title="Refresh list"
        >↺</button>
      </div>

      <div class="doc-list">
        {#if docStore.documents.length === 0}
          <p class="empty-hint">No documents yet — add some above.</p>
        {:else}
          {#each docStore.documents as doc (doc.document_id)}
            <DocumentCard {doc} />
          {/each}
        {/if}
      </div>
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
    width: 420px;
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

  .panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: -4px;
  }

  .doc-list-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .doc-count {
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 500;
  }

  .refresh-btn {
    font-size: 16px;
    color: var(--text-muted);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    transition: color 0.15s, background 0.15s;
  }
  .refresh-btn:hover { color: var(--accent); background: var(--bg-primary); }

  .doc-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .empty-hint {
    font-size: 13px;
    color: var(--text-muted);
    text-align: center;
    padding: 24px 0;
  }
</style>
