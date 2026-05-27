<script lang="ts">
  import { onMount } from 'svelte';
  import { chatStore } from '$lib/stores/sessions.svelte';
  import { uiStore } from '$lib/stores/ui.svelte';

  onMount(() => {
    chatStore.loadSessions();
  });

  function newChat() {
    chatStore.createSession();
  }

  function selectSession(id: string) {
    chatStore.setActiveSession(id);
  }

  async function deleteSession(e: MouseEvent, id: string) {
    e.stopPropagation();
    await chatStore.deleteSession(id);
  }
</script>

<aside class="sidebar">
  <header class="brand">
    <span class="logo">⚡</span>
    {#if !uiStore.sidebarCollapsed}
      <span class="name">Hermes</span>
    {/if}
  </header>

  <button class="new-chat" onclick={newChat} title="New Chat">
    <span class="plus">＋</span>
    {#if !uiStore.sidebarCollapsed}
      <span>New Chat</span>
    {/if}
  </button>

  <nav class="session-list">
    {#each chatStore.sessions as session (session.id)}
      <div
        class="session-item"
        class:active={chatStore.activeSessionId === session.id}
        role="button"
        tabindex="0"
        onclick={() => selectSession(session.id)}
        onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && selectSession(session.id)}
        title={session.title}
      >
        {#if uiStore.sidebarCollapsed}
          <span class="dot"></span>
        {:else}
          <span class="session-title">{session.title}</span>
          <button
            class="delete-btn"
            onclick={(e) => deleteSession(e, session.id)}
            title="Delete chat"
            aria-label="Delete chat"
          >✕</button>
        {/if}
      </div>
    {/each}
  </nav>

  <footer class="sidebar-footer">
    <button
      class="icon-btn"
      onclick={() => (uiStore.showDocManager = !uiStore.showDocManager)}
      title="Documents"
    >📄</button>
    <button
      class="icon-btn"
      onclick={() => (uiStore.showSettings = !uiStore.showSettings)}
      title="Settings"
    >⚙</button>
    <button
      class="icon-btn collapse-btn"
      onclick={() => (uiStore.sidebarCollapsed = !uiStore.sidebarCollapsed)}
      title={uiStore.sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
    >{uiStore.sidebarCollapsed ? '›' : '‹'}</button>
  </footer>
</aside>

<style>
  .sidebar {
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    height: 100vh;
    overflow: hidden;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 16px 12px;
    border-bottom: 1px solid var(--border);
    min-height: 56px;
    overflow: hidden;
  }

  .logo { font-size: 20px; flex-shrink: 0; }

  .name {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
  }

  .new-chat {
    display: flex;
    align-items: center;
    gap: 8px;
    width: calc(100% - 16px);
    margin: 12px 8px;
    padding: 8px 12px;
    background: var(--accent);
    color: white;
    border-radius: var(--radius-md);
    font-weight: 500;
    justify-content: center;
    transition: opacity 0.15s;
    white-space: nowrap;
    overflow: hidden;
  }

  .new-chat:hover { opacity: 0.85; }
  .plus { flex-shrink: 0; }

  .session-list {
    flex: 1;
    overflow-y: auto;
    padding: 4px 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 8px 10px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    text-align: left;
    transition: background 0.1s, color 0.1s;
    cursor: pointer;
    min-height: 36px;
    user-select: none;
  }

  .session-item:hover { background: var(--bg-primary); color: var(--text-primary); }
  .session-item.active { background: var(--bg-chat); color: var(--text-primary); }
  .session-item:hover .delete-btn { opacity: 1; }

  .session-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 13px;
  }

  .delete-btn {
    opacity: 0;
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-size: 11px;
    flex-shrink: 0;
    transition: opacity 0.15s, color 0.15s;
  }
  .delete-btn:hover { color: var(--error); }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--border);
    margin: 0 auto;
  }

  .sidebar-footer {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px;
    border-top: 1px solid var(--border);
    flex-wrap: nowrap;
  }

  .icon-btn {
    padding: 8px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-size: 16px;
    transition: color 0.15s, background 0.15s;
    flex-shrink: 0;
  }
  .icon-btn:hover { color: var(--text-primary); background: var(--bg-primary); }
  .collapse-btn { margin-left: auto; }
</style>
