import { apiBase } from '$lib/backend.svelte';
import { apiFetch } from './client';

export interface ChatChunk {
  type: 'text' | 'done' | 'error';
  data: string;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
}

/**
 * Validate chat LLM connectivity for a specific provider by making
 * a real non-streaming /api/chat request.
 */
export function testProviderChat(provider: string): Promise<ChatResponse> {
  return apiFetch('/api/chat', {
    method: 'POST',
    body: JSON.stringify({
      message: 'Reply with exactly: OK',
      provider,
      stream: false,
    }),
  });
}

/**
 * Stream a chat response from the backend via SSE.
 * Yields ChatChunks until 'done' or 'error', or the signal is aborted.
 */
export async function* streamChat(
  message: string,
  sessionId: string,
  signal?: AbortSignal,
  provider?: string,
): AsyncGenerator<ChatChunk> {
  let res: Response;
  try {
    res = await fetch(`${apiBase()}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        stream: true,
        ...(provider ? { provider } : {}),
      }),
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') return;
    yield { type: 'error', data: 'Failed to connect to backend.' };
    return;
  }

  if (!res.ok || !res.body) {
    yield { type: 'error', data: `HTTP ${res.status}` };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const payload = JSON.parse(line.slice(6)) as Record<string, unknown>;
          if (typeof payload.token === 'string') {
            yield { type: 'text', data: payload.token };
          } else if (payload.done) {
            yield { type: 'done', data: '' };
            return;
          } else if (typeof payload.error === 'string') {
            yield { type: 'error', data: payload.error };
            return;
          }
        } catch {
          // malformed SSE line — skip
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
