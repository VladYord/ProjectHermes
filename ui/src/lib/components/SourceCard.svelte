<script lang="ts">
  interface Props {
    name: string;
    score: number;
    excerpt: string;
  }

  let { name, score, excerpt }: Props = $props();

  let expanded = $state(false);
  let pct = $derived(Math.round(score * 100));
</script>

<div
  class="source-card"
  role="button"
  tabindex="0"
  onclick={() => (expanded = !expanded)}
  onkeydown={(e) => e.key === 'Enter' && (expanded = !expanded)}
>
  <div class="source-header">
    <span class="source-name">📄 {name}</span>
    <span class="source-score">{pct}%</span>
  </div>
  <div class="score-bar">
    <div class="score-fill" style="width: {pct}%"></div>
  </div>
  <p class="excerpt" class:expanded>{excerpt}</p>
</div>

<style>
  .source-card {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    cursor: pointer;
    transition: border-color 0.15s;
  }
  .source-card:hover { border-color: var(--accent); }

  .source-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }

  .source-name {
    font-size: 12px;
    color: var(--text-primary);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 70%;
  }

  .source-score {
    font-size: 11px;
    color: var(--accent);
    font-weight: 600;
    flex-shrink: 0;
  }

  .score-bar {
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    margin-bottom: 6px;
  }

  .score-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
  }

  .excerpt {
    font-size: 12px;
    color: var(--text-muted);
    margin: 0;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    line-height: 1.5;
  }

  .excerpt.expanded {
    display: block;
    -webkit-line-clamp: unset;
    line-clamp: unset;
  }
</style>
