import { apiBase } from '$lib/backend.svelte';
import { apiFetch } from './client';

/** Matches backend `DocumentInfo` schema. */
export interface DocumentInfo {
  document_id: string;
  name: string;
  doc_type: string;
  chunks_count: number;
  ingested_at: string; // ISO datetime string
}

/** Matches backend `IngestResponse` schema. */
export interface IngestResponse {
  document_id: string;
  document_name: string;
  chunks_created: number;
  processing_time_seconds: number;
}

export function listDocuments(): Promise<{ documents: DocumentInfo[] }> {
  return apiFetch('/api/documents');
}

/** Upload a file for ingestion — multipart/form-data, field name "file". */
export async function uploadDocument(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append('file', file, file.name);

  const res = await fetch(`${apiBase()}/api/ingest/upload`, {
    method: 'POST',
    body: form,
    // Do NOT set Content-Type — let the browser set it with the boundary
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Upload failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<IngestResponse>;
}

export function deleteDocument(id: string): Promise<unknown> {
  return apiFetch(`/api/documents/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

/**
 * Ingest a document by its file-system path.
 * Used in Tauri production mode where the native file dialog returns a path,
 * not file bytes. The Python sidecar reads the file directly.
 */
export function ingestByPath(filePath: string): Promise<IngestResponse> {
  return apiFetch('/api/ingest', {
    method: 'POST',
    body: JSON.stringify({ file_path: filePath }),
  });
}
