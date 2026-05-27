<script lang="ts">
  import { docStore } from '$lib/stores/documents.svelte';

  const ACCEPT =
    '.pdf,.txt,.md,.docx,.py,.js,.ts,.jsx,.tsx,.java,.c,.cpp,.h,.cs,.go,.rs,' +
    '.png,.jpg,.jpeg,.tiff,.bmp';

  let inputEl = $state<HTMLInputElement | null>(null);

  function openPicker() {
    inputEl?.click();
  }

  async function onFilesSelected(e: Event) {
    const input = e.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = ''; // Reset so same file can be re-selected
    for (const file of files) {
      await docStore.uploadAndIngest(file);
    }
  }
</script>

<!-- Hidden file input — replaced with Tauri dialog.open() in Phase 5 -->
<input
  bind:this={inputEl}
  type="file"
  multiple
  accept={ACCEPT}
  onchange={onFilesSelected}
  style="display: none;"
  aria-hidden="true"
/>

<button class="upload-btn" onclick={openPicker} title="Supported: {ACCEPT}">
  <span class="plus">＋</span>
  Add Documents
</button>

<style>
  .upload-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 10px 14px;
    background: var(--bg-primary);
    border: 1px dashed var(--border);
    border-radius: var(--radius-md);
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    transition: border-color 0.15s, color 0.15s;
    cursor: pointer;
  }
  .upload-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .plus { font-size: 16px; }
</style>
