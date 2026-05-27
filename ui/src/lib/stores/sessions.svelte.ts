import { streamChat } from '$lib/api/chat';
import {
  deleteSession as apiDelete,
  getSessionHistory,
  listSessions as apiList,
} from '$lib/api/sessions';

export interface SourceRef {
  document: string;
  chunk: string;
  score: number;
}

export interface UIMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources: SourceRef[];
}

export interface SessionMeta {
  id: string;
  title: string;
}

class SessionsStore {
  sessions = $state<SessionMeta[]>([]);
  activeSessionId = $state<string | null>(null);
  messages = $state<UIMessage[]>([]);
  isStreaming = $state(false);

  private abortController: AbortController | null = null;

  async loadSessions(): Promise<void> {
    try {
      const { sessions } = await apiList();
      const existingMap = new Map(this.sessions.map((s) => [s.id, s]));
      const merged: SessionMeta[] = sessions.map(
        (id) => existingMap.get(id) ?? { id, title: 'Chat' },
      );
      // Prepend any local-only sessions (created before backend registered them)
      for (const s of this.sessions) {
        if (!merged.some((m) => m.id === s.id)) merged.unshift(s);
      }
      this.sessions = merged;
    } catch {
      // Backend not running yet — keep current state
    }
  }

  createSession(): void {
    const id = crypto.randomUUID();
    this.sessions = [{ id, title: 'New Chat' }, ...this.sessions];
    this.activeSessionId = id;
    this.messages = [];
  }

  async setActiveSession(id: string): Promise<void> {
    if (this.isStreaming) return;
    this.activeSessionId = id;
    try {
      const hist = await getSessionHistory(id);
      this.messages = hist.messages.map((m) => ({
        id: crypto.randomUUID(),
        role: (m.role === 'human' ? 'user' : 'assistant') as 'user' | 'assistant',
        content: m.content,
        sources: [],
      }));
    } catch {
      this.messages = [];
    }
  }

  async deleteSession(id: string): Promise<void> {
    try {
      await apiDelete(id);
    } catch {
      // Ignore 404 — session may not have been saved to backend yet
    }
    this.sessions = this.sessions.filter((s) => s.id !== id);
    if (this.activeSessionId === id) {
      const next = this.sessions[0] ?? null;
      if (next) {
        await this.setActiveSession(next.id);
      } else {
        this.activeSessionId = null;
        this.messages = [];
      }
    }
  }

  async sendMessage(text: string): Promise<void> {
    // Cancel any in-flight stream before starting a new one
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }

    if (!this.activeSessionId) this.createSession();
    const sessionId = this.activeSessionId!;

    // Add the user message
    this.messages = [
      ...this.messages,
      { id: crypto.randomUUID(), role: 'user', content: text, sources: [] },
    ];

    // Auto-title the session from the first user message
    const session = this.sessions.find((s) => s.id === sessionId);
    if (session && session.title === 'New Chat') {
      session.title = text.length > 40 ? text.slice(0, 40) + '…' : text;
    }

    // Add empty assistant placeholder (shows StreamingDots until content arrives)
    this.messages = [
      ...this.messages,
      { id: crypto.randomUUID(), role: 'assistant', content: '', sources: [] },
    ];
    this.isStreaming = true;
    this.abortController = new AbortController();

    try {
      for await (const chunk of streamChat(text, sessionId, this.abortController.signal)) {
        if (chunk.type === 'text') {
          const last = this.messages.at(-1);
          if (last?.role === 'assistant') last.content += chunk.data;
        } else if (chunk.type === 'error') {
          const last = this.messages.at(-1);
          if (last?.role === 'assistant') last.content = `Error: ${chunk.data}`;
          break;
        } else if (chunk.type === 'done') {
          break;
        }
      }

      // If stream closed without text or explicit error, surface a clear hint.
      const last = this.messages.at(-1);
      if (last?.role === 'assistant' && last.content.trim() === '') {
        last.content =
          'No response received from LLM. Open Settings and run Test Connection for your provider.';
      }
    } catch (err: unknown) {
      const isAbort = err instanceof Error && err.name === 'AbortError';
      if (!isAbort) {
        const last = this.messages.at(-1);
        if (last?.role === 'assistant' && last.content === '') {
          last.content = 'Connection error — is the backend running on port 8000?';
        }
      }
    } finally {
      this.isStreaming = false;
      this.abortController = null;
    }
  }
}

export const chatStore = new SessionsStore();
