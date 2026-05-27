import {
  getConfig,
  getHealth,
  getProviders,
  patchConfig,
  type AppConfig,
  type ProviderPatch,
  type ProviderStatus,
} from '$lib/api/config';

export type { AppConfig, ProviderStatus };

class ConfigStore {
  config = $state<AppConfig | null>(null);
  providers = $state<ProviderStatus[]>([]);
  isSaving = $state(false);
  saveError = $state<string | null>(null);
  loadError = $state<string | null>(null);
  backendVersion = $state<string | null>(null);

  async load(): Promise<void> {
    this.loadError = null;
    try {
      const [cfg, prov] = await Promise.all([getConfig(), getProviders()]);
      this.config = cfg;
      this.providers = prov.providers;
    } catch (err: unknown) {
      this.loadError = err instanceof Error ? err.message : String(err);
      // Keep previous config if any; if none exists, panel will show loading+error.
    }
  }

  async refreshProviders(): Promise<void> {
    try {
      const prov = await getProviders();
      this.providers = prov.providers;
      // Also sync reachability into config if needed
    } catch {
      // ignore
    }
  }

  async saveProvider(name: string, patch: ProviderPatch): Promise<void> {
    this.isSaving = true;
    this.saveError = null;
    try {
      const updated = await patchConfig({ providers: { [name]: patch } });
      this.config = updated;
    } catch (err: unknown) {
      this.saveError = err instanceof Error ? err.message : String(err);
    } finally {
      this.isSaving = false;
    }
  }

  async setDefaultProvider(provider: string): Promise<void> {
    this.isSaving = true;
    this.saveError = null;
    try {
      const updated = await patchConfig({ default_provider: provider });
      this.config = updated;
    } catch (err: unknown) {
      this.saveError = err instanceof Error ? err.message : String(err);
    } finally {
      this.isSaving = false;
    }
  }

  async setEmbeddingProvider(provider: string): Promise<void> {
    this.isSaving = true;
    this.saveError = null;
    try {
      const updated = await patchConfig({ embedding_provider: provider });
      this.config = updated;
    } catch (err: unknown) {
      this.saveError = err instanceof Error ? err.message : String(err);
    } finally {
      this.isSaving = false;
    }
  }

  async fetchBackendVersion(): Promise<void> {
    try {
      const health = await getHealth();
      this.backendVersion = health.version;
    } catch {
      this.backendVersion = null;
    }
  }
}

export const configStore = new ConfigStore();
