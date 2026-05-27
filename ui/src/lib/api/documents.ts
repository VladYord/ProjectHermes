import { apiFetch } from './client';

export interface DocumentInfo {
  document_id: string;
  name: string;
  doc_type: string;
  chunks_count: number;
  ingested_at: string;
}

/** Stub — full implementation in Phase 3. */
export function listDocuments(): Promise<{ documents: DocumentInfo[] }> {
  return apiFetch('/api/documents');
}
