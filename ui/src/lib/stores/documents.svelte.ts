import {
  deleteDocument as apiDelete,
  ingestByPath as apiIngestByPath,
  listDocuments as apiList,
  uploadDocument as apiUpload,
  type DocumentInfo,
} from '$lib/api/documents';

export type { DocumentInfo };

export type UploadProgress = 'uploading' | 'processing' | 'done' | 'error';

export interface UploadState {
  active: boolean;
  filename: string;
  progress: UploadProgress;
  chunksCreated?: number;
  error?: string;
}

class DocumentsStore {
  documents = $state<DocumentInfo[]>([]);
  uploadState = $state<UploadState>({
    active: false,
    filename: '',
    progress: 'done',
  });

  private pollTimer: ReturnType<typeof setInterval> | null = null;

  async refreshDocuments(): Promise<void> {
    try {
      const { documents } = await apiList();
      this.documents = documents;
    } catch {
      // Backend not running — leave current state
    }
  }

  async uploadAndIngest(file: File): Promise<void> {
    this.uploadState = { active: true, filename: file.name, progress: 'uploading' };

    let result;
    try {
      result = await apiUpload(file);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.uploadState = { active: true, filename: file.name, progress: 'error', error: msg };
      return;
    }

    // Switch to processing while we wait for the document to appear in the list
    this.uploadState = {
      active: true,
      filename: file.name,
      progress: 'processing',
      chunksCreated: result.chunks_created,
    };

    // Immediately refresh — upload endpoint is synchronous so the doc is already there
    await this.refreshDocuments();

    this.uploadState = {
      active: true,
      filename: file.name,
      progress: 'done',
      chunksCreated: result.chunks_created,
    };

    // Auto-dismiss the success banner after 3 seconds
    setTimeout(() => {
      if (this.uploadState.progress === 'done') {
        this.uploadState = { active: false, filename: '', progress: 'done' };
      }
    }, 3000);
  }

  async removeDocument(id: string): Promise<void> {
    try {
      await apiDelete(id);
      this.documents = this.documents.filter((d) => d.document_id !== id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('Failed to delete document:', msg);
    }
  }

  dismissUpload(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    this.uploadState = { active: false, filename: '', progress: 'done' };
  }

  /**
   * Ingest a file by its native filesystem path (Tauri production mode).
   * Called after Tauri dialog.open() returns a path string.
   */
  async ingestByPath(filePath: string): Promise<void> {
    const filename = filePath.replace(/\\/g, '/').split('/').pop() ?? filePath;
    this.uploadState = { active: true, filename, progress: 'uploading' };
    try {
      const result = await apiIngestByPath(filePath);
      await this.refreshDocuments();
      this.uploadState = {
        active: true,
        filename,
        progress: 'done',
        chunksCreated: result.chunks_created,
      };
      setTimeout(() => {
        if (this.uploadState.progress === 'done') {
          this.uploadState = { active: false, filename: '', progress: 'done' };
        }
      }, 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.uploadState = { active: true, filename, progress: 'error', error: msg };
    }
  }
}

export const docStore = new DocumentsStore();
