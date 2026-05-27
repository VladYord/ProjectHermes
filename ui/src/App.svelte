<script lang="ts">
  import { onMount } from 'svelte';
  import AppLayout from '$lib/components/AppLayout.svelte';
  import { backend, initBackend } from '$lib/backend.svelte';

  let startError = $state<string | null>(null);

  onMount(async () => {
    startError = await initBackend();
  });
</script>

{#if startError}
  <!-- Backend failed to start -->
  <div class="splash error">
    <span class="splash-icon">⚠</span>
    <p class="splash-title">Backend failed to start</p>
    <p class="splash-msg">{startError}</p>
    <button
      class="retry-btn"
      onclick={async () => { startError = null; startError = await initBackend(); }}
    >Retry</button>
  </div>

{:else if !backend.ready}
  <!-- Loading screen while backend starts -->
  <div class="splash">
    <span class="splash-icon">⚡</span>
    <p class="splash-title">Hermes</p>
    <p class="splash-msg">Starting backend…</p>
    <div class="dots">
      <span class="dot"></span>
      <span class="dot"></span>
      <span class="dot"></span>
    </div>
  </div>

{:else}
  <AppLayout />
{/if}

<style>
  .splash {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    gap: 12px;
    background: var(--bg-primary);
    animation: fade-in 0.3s ease;
  }

  @keyframes fade-in {
    from { opacity: 0; }
    to   { opacity: 1; }
  }

  .splash-icon { font-size: 48px; }

  .splash-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
  }

  .splash-msg {
    font-size: 13px;
    color: var(--text-muted);
    margin: 0;
    text-align: center;
    max-width: 360px;
    line-height: 1.5;
  }

  /* Animated dots (reuses StreamingDots pattern) */
  .dots {
    display: flex;
    gap: 6px;
    margin-top: 4px;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    animation: bounce 1.2s infinite ease-in-out;
  }
  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40%            { transform: scale(1);   opacity: 1;   }
  }

  .error .splash-icon { filter: grayscale(1); }

  .retry-btn {
    margin-top: 8px;
    padding: 8px 20px;
    background: var(--accent);
    color: white;
    border-radius: var(--radius-md);
    font-size: 13px;
    font-weight: 500;
    transition: opacity 0.15s;
  }
  .retry-btn:hover { opacity: 0.85; }
</style>

