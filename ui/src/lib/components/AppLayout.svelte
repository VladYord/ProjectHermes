<script lang="ts">
  import ChatSidebar from './ChatSidebar.svelte';
  import ChatWindow from './ChatWindow.svelte';
  import DocumentManager from './DocumentManager.svelte';
  import SettingsPanel from './SettingsPanel.svelte';
  import { uiStore } from '$lib/stores/ui.svelte';
</script>

<div class="layout" class:collapsed={uiStore.sidebarCollapsed}>
  <ChatSidebar />
  <ChatWindow />
</div>

<!-- Overlay panels — rendered outside the grid so they float above everything -->
<DocumentManager />
<SettingsPanel />

<style>
  .layout {
    display: grid;
    grid-template-columns: var(--sidebar-width) 1fr;
    height: 100vh;
    overflow: hidden;
    background: var(--bg-primary);
  }

  .layout.collapsed {
    grid-template-columns: 48px 1fr;
  }

  @media (max-width: 800px) {
    .layout {
      grid-template-columns: 48px 1fr;
    }
  }
</style>
