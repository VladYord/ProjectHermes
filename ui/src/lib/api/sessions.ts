import { apiFetch } from './client';

export interface Message {
  role: string;
  content: string;
}

export interface SessionHistoryResponse {
  session_id: string;
  messages: Message[];
}

export function listSessions(): Promise<{ sessions: string[] }> {
  return apiFetch('/api/sessions');
}

export function getSessionHistory(id: string): Promise<SessionHistoryResponse> {
  return apiFetch(`/api/sessions/${encodeURIComponent(id)}/history`);
}

export function deleteSession(id: string): Promise<unknown> {
  return apiFetch(`/api/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' });
}
