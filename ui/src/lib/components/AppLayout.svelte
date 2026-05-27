<script lang="ts">
  import ChatSidebar from './ChatSidebar.svelte';
  import ChatWindow from './ChatWindow.svelte';
  import DocumentManager from './DocumentManager.svelte';
  import { uiStore } from '$lib/stores/ui.svelte';
</script>

<div class="layout" class:collapsed={uiStore.sidebarCollapsed}>
  <ChatSidebar />
  <ChatWindow />
</div>

<!-- DocumentManager renders as a fixed overlay — outside the grid -->
<DocumentManager />

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
