import { apiFetch } from './client';

export interface AppConfig {
  default_provider: string;
  embedding_provider: string;
  providers: Record<string, unknown>;
}

/** Stub — full implementation in Phase 4. */
export function getConfig(): Promise<AppConfig> {
  return apiFetch('/api/config');
}
