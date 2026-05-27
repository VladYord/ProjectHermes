<script lang="ts">
  import { docStore } from '$lib/stores/documents.svelte';

  const s = $derived(docStore.uploadState);
</script>

{#if s.active}
  <div class="progress-bar" class:error={s.progress === 'error'} class:done={s.progress === 'done'}>
    {#if s.progress === 'uploading'}
      <span class="spinner">⟳</span>
      <span class="label">Uploading <strong>{s.filename}</strong>…</span>
    {:else if s.progress === 'processing'}
      <div class="indeterminate"></div>
      <span class="label">Processing <strong>{s.filename}</strong>…</span>
    {:else if s.progress === 'done'}
      <span class="icon success">✓</span>
      <span class="label">
        <strong>{s.filename}</strong> added
        {#if s.chunksCreated !== undefined}({s.chunksCreated} chunks){/if}
      </span>
    {:else if s.progress === 'error'}
      <span class="icon error-icon">✕</span>
      <span class="label error-text">{s.error ?? 'Upload failed'}</span>
    {/if}

    <button class="dismiss" onclick={() => docStore.dismissUpload()} title="Dismiss">✕</button>
  </div>
{/if}

<style>
  .progress-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: 12px;
    color: var(--text-muted);
    position: relative;
    overflow: hidden;
  }

  .progress-bar.done { border-color: var(--success); }
  .progress-bar.error { border-color: var(--error); }

  .indeterminate {
    position: absolute;
    left: 0;
    bottom: 0;
    height: 2px;
    width: 40%;
    background: var(--accent);
    border-radius: 0 2px 2px 0;
    animation: slide 1.5s ease-in-out infinite;
  }

  @keyframes slide {
    0%   { left: -40%; }
    100% { left: 100%; }
  }

  .spinner {
    display: inline-block;
    animation: spin 1s linear infinite;
    font-size: 14px;
    flex-shrink: 0;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .icon { font-size: 14px; flex-shrink: 0; }
  .success { color: var(--success); }
  .error-icon { color: var(--error); }
  .error-text { color: var(--error); }

  .label { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .label strong { color: var(--text-primary); }

  .dismiss {
    flex-shrink: 0;
    font-size: 11px;
    color: var(--text-muted);
    padding: 2px 4px;
    border-radius: var(--radius-sm);
    transition: color 0.15s;
  }
  .dismiss:hover { color: var(--text-primary); }
</style>
