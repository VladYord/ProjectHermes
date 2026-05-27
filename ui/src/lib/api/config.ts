import { apiFetch } from './client';

/** Shape of each provider block returned by GET /api/config */
export interface ProviderConfig {
  model?: string;
  deployment?: string;       // azure_openai uses deployment instead of model
  api_key_set?: boolean;
  base_url?: string;
  embedding_model?: string;
  embedding_deployment?: string;
  api_version?: string;
}

export interface AppConfig {
  default_provider: string;
  embedding_provider: string;
  providers: Record<string, ProviderConfig>;
}

/** Live status returned by GET /api/providers */
export interface ProviderStatus {
  name: string;
  available: boolean;
  reachable: boolean | null;
  latency_ms: number | null;
  api_key_set: boolean;
  model: string | null;
}

export interface ProvidersResponse {
  default: string;
  providers: ProviderStatus[];
}

export interface HealthResponse {
  status: string;
  version: string;
}

/** Fields accepted by PATCH /api/config providers entries */
export interface ProviderPatch {
  api_key?: string;
  model?: string;
  base_url?: string;
  deployment?: string;
  api_version?: string;
  embedding_deployment?: string;
  embedding_model?: string;
}

export interface ConfigPatch {
  default_provider?: string;
  embedding_provider?: string;
  providers?: Record<string, ProviderPatch>;
}

export function getConfig(): Promise<AppConfig> {
  return apiFetch('/api/config');
}

export function patchConfig(patch: ConfigPatch): Promise<AppConfig> {
  return apiFetch('/api/config', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

export function getProviders(): Promise<ProvidersResponse> {
  return apiFetch('/api/providers');
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch('/api/health');
}
