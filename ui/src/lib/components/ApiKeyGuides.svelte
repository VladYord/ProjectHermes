<script lang="ts">
  const GUIDES = [
    {
      name: 'OpenAI',
      icon: '🤖',
      url: 'https://platform.openai.com/api-keys',
      desc: 'Create an OpenAI API key (GPT-4o, o3, etc.)',
    },
    {
      name: 'Google Gemini',
      icon: '✨',
      url: 'https://aistudio.google.com/app/apikey',
      desc: 'Get a free Gemini API key via Google AI Studio',
    },
    {
      name: 'Ollama',
      icon: '🦙',
      url: 'https://ollama.com/download',
      desc: 'Run open-source models locally — completely free',
    },
  ];

  function openLink(url: string) {
    if ((window as { __TAURI_INTERNALS__?: object }).__TAURI_INTERNALS__) {
      // Production: open in system default browser via Tauri shell plugin
      import('@tauri-apps/plugin-shell').then(({ open }) => open(url));
    } else {
      // Dev mode: standard browser open
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  }
</script>

<div class="guides">
  <p class="section-title">🔑 How to get API keys</p>
  <div class="guide-cards">
    {#each GUIDES as guide}
      <div class="guide-card">
        <span class="guide-icon">{guide.icon}</span>
        <div class="guide-info">
          <span class="guide-name">{guide.name}</span>
          <span class="guide-desc">{guide.desc}</span>
        </div>
        <button class="guide-link" onclick={() => openLink(guide.url)}>
          Get Key ↗
        </button>
      </div>
    {/each}
  </div>
</div>

<style>
  .guides {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .guide-cards {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .guide-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .guide-icon { font-size: 18px; flex-shrink: 0; }

  .guide-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .guide-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .guide-desc {
    font-size: 11px;
    color: var(--text-muted);
  }

  .guide-link {
    flex-shrink: 0;
    font-size: 12px;
    color: var(--accent);
    padding: 4px 8px;
    border: 1px solid var(--accent);
    border-radius: var(--radius-sm);
    transition: background 0.15s;
  }
  .guide-link:hover { background: rgba(79, 142, 247, 0.1); }
</style>
