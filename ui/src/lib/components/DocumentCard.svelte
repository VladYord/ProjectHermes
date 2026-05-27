<script lang="ts">
  import type { DocumentInfo } from '$lib/stores/documents.svelte';
  import { docStore } from '$lib/stores/documents.svelte';

  interface Props {
    doc: DocumentInfo;
  }

  let { doc }: Props = $props();

  let confirming = $state(false);

  function typeIcon(docType: string): string {
    const t = docType.toLowerCase();
    if (t === 'pdf') return '📄';
    if (t === 'markdown' || t === 'text') return '📝';
    if (['python', 'javascript', 'typescript', 'java', 'c', 'cpp', 'csharp', 'go', 'rust'].includes(t))
      return '💻';
    if (['png', 'jpg', 'jpeg', 'tiff', 'bmp', 'image'].includes(t)) return '🖼';
    return '📎';
  }

  function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return 'just now';
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  async function confirmDelete() {
    if (!confirming) { confirming = true; return; }
    await docStore.removeDocument(doc.document_id);
  }

  function cancelDelete() {
    confirming = false;
  }
</script>

<div class="doc-card">
  <span class="doc-icon">{typeIcon(doc.doc_type)}</span>
  <div class="doc-info">
    <span class="doc-name" title={doc.name}>{doc.name}</span>
    <span class="doc-meta">
      {doc.doc_type} · {doc.chunks_count} chunk{doc.chunks_count === 1 ? '' : 's'} · {relativeTime(doc.ingested_at)}
    </span>
  </div>
  <div class="doc-actions">
    {#if confirming}
      <span class="confirm-label">Delete?</span>
      <button class="action-btn confirm-yes" onclick={confirmDelete} title="Confirm delete">✓</button>
      <button class="action-btn confirm-no" onclick={cancelDelete} title="Cancel">✕</button>
    {:else}
      <button class="action-btn delete-btn" onclick={confirmDelete} title="Delete document">🗑</button>
    {/if}
  </div>
</div>

<style>
  .doc-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    transition: border-color 0.15s;
  }
  .doc-card:hover { border-color: var(--accent); }

  .doc-icon { font-size: 18px; flex-shrink: 0; }

  .doc-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .doc-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .doc-meta {
    font-size: 11px;
    color: var(--text-muted);
  }

  .doc-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .action-btn {
    padding: 4px 6px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    color: var(--text-muted);
    transition: color 0.15s, background 0.15s;
  }
  .action-btn:hover { background: var(--bg-secondary); }
  .delete-btn:hover { color: var(--error); }

  .confirm-label {
    font-size: 11px;
    color: var(--warning);
    white-space: nowrap;
  }

  .confirm-yes { color: var(--success); }
  .confirm-yes:hover { color: var(--success); background: var(--bg-secondary); }
  .confirm-no:hover { color: var(--error); }
</style>
