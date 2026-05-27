<script lang="ts">
  import { chatStore } from '$lib/stores/sessions.svelte';
  import MessageBubble from './MessageBubble.svelte';

  let messagesEl = $state<HTMLDivElement | null>(null);
  let inputText = $state('');
  let textareaEl = $state<HTMLTextAreaElement | null>(null);

  function scrollToBottom() {
    requestAnimationFrame(() => {
      messagesEl?.scrollTo({ top: messagesEl.scrollHeight, behavior: 'smooth' });
    });
  }

  $effect(() => {
    // Re-track on any message content change or streaming state change
    chatStore.messages.length;
    chatStore.isStreaming;
    scrollToBottom();
  });

  function autoResize() {
    if (!textareaEl) return;
    textareaEl.style.height = 'auto';
    textareaEl.style.height = Math.min(textareaEl.scrollHeight, 120) + 'px';
  }

  async function send() {
    const text = inputText.trim();
    if (!text || chatStore.isStreaming) return;
    inputText = '';
    if (textareaEl) textareaEl.style.height = 'auto';
    await chatStore.sendMessage(text);
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }
</script>

<section class="chat-window">
  <div class="messages" bind:this={messagesEl}>
    {#if chatStore.messages.length === 0 && !chatStore.isStreaming}
      <div class="empty-state">
        <p class="hint">⚡ Ask Hermes anything about your documents</p>
      </div>
    {/if}

    {#each chatStore.messages as msg (msg.id)}
      <MessageBubble
        role={msg.role}
        content={msg.content}
        sources={msg.sources}
        isStreaming={chatStore.isStreaming &&
          msg === chatStore.messages.at(-1) &&
          msg.role === 'assistant' &&
          msg.content === ''}
      />
    {/each}
  </div>

  <div class="composer">
    <textarea
      bind:this={textareaEl}
      bind:value={inputText}
      oninput={autoResize}
      onkeydown={onKeydown}
      placeholder="Ask Hermes anything…"
      rows={1}
      disabled={chatStore.isStreaming}
    ></textarea>
    <button
      class="send-btn"
      onclick={send}
      disabled={!inputText.trim() || chatStore.isStreaming}
      title="Send message"
    >↑</button>
  </div>
</section>

<style>
  .chat-window {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--bg-chat);
    overflow: hidden;
  }

  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .empty-state {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    margin: auto 0;
  }

  .hint {
    color: var(--text-muted);
    font-size: 15px;
  }

  .composer {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    padding: 12px 16px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border);
  }

  textarea {
    flex: 1;
    background: var(--bg-primary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 10px 14px;
    resize: none;
    outline: none;
    line-height: 1.5;
    max-height: 120px;
    overflow-y: auto;
    transition: border-color 0.15s;
  }

  textarea::placeholder { color: var(--text-muted); }
  textarea:focus { border-color: var(--accent); }
  textarea:disabled { opacity: 0.5; cursor: not-allowed; }

  .send-btn {
    width: 38px;
    height: 38px;
    background: var(--accent);
    color: white;
    border-radius: var(--radius-md);
    font-size: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: opacity 0.15s;
  }

  .send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .send-btn:not(:disabled):hover { opacity: 0.85; }
</style>
