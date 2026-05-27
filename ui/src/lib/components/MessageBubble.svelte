<script lang="ts">
  import SourceCard from './SourceCard.svelte';
  import StreamingDots from './StreamingDots.svelte';
  import type { SourceRef } from '$lib/stores/sessions.svelte';

  interface Props {
    role: 'user' | 'assistant';
    content: string;
    sources: SourceRef[];
    isStreaming?: boolean;
  }

  let { role, content, sources, isStreaming = false }: Props = $props();

  let sourcesExpanded = $state(false);
</script>

<div class="bubble-wrap" class:user={role === 'user'} class:assistant={role === 'assistant'}>
  <div class="bubble">
    {#if isStreaming && content === ''}
      <StreamingDots />
    {:else}
      <p class="content">{content}</p>
    {/if}

    {#if sources.length > 0}
      <div class="sources-section">
        <button
          class="sources-toggle"
          onclick={() => (sourcesExpanded = !sourcesExpanded)}
        >
          {sourcesExpanded ? '▼' : '▶'} Sources ({sources.length})
        </button>
        {#if sourcesExpanded}
          <div class="sources-list">
            {#each sources as source (source.document + source.score)}
              <SourceCard
                name={source.document}
                score={source.score}
                excerpt={source.chunk}
              />
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .bubble-wrap {
    display: flex;
    max-width: 75%;
  }

  .bubble-wrap.user {
    align-self: flex-end;
    margin-left: auto;
  }

  .bubble-wrap.assistant {
    align-self: flex-start;
    margin-right: auto;
  }

  .bubble {
    padding: 10px 14px;
    border-radius: var(--radius-lg);
    font-size: 14px;
    line-height: 1.6;
    word-break: break-word;
  }

  .user .bubble {
    background: var(--user-bubble);
    color: var(--text-primary);
    border-bottom-right-radius: var(--radius-sm);
  }

  .assistant .bubble {
    background: var(--ai-bubble);
    color: var(--text-primary);
    border-bottom-left-radius: var(--radius-sm);
  }

  .content {
    white-space: pre-wrap;
    margin: 0;
  }

  .sources-section {
    margin-top: 8px;
    border-top: 1px solid var(--border);
    padding-top: 8px;
  }

  .sources-toggle {
    color: var(--text-muted);
    font-size: 12px;
    padding: 2px 0;
    transition: color 0.15s;
  }
  .sources-toggle:hover { color: var(--accent); }

  .sources-list {
    margin-top: 6px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
</style>
