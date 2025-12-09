export type FileFormat = 'pdf' | 'txt' | 'md';

export interface UploadedFile {
  id: string;
  filename: string;
  size: number;
  format: FileFormat;
  uploadedAt: Date;
  status: 'uploading' | 'processing' | 'success' | 'error';
  progress: number;
  errorMessage?: string;
  documentId?: string;
  ingestionId?: string;
  originalFile?: File;
}

export interface UploadResponse {
  ingestionId: string;
  files: Array<{
    documentId: string;
    filename: string;
    size: number;
    uploadedAt: string;
    status: 'success' | 'failed';
    message?: string;
  }>;
}

export const SUPPORTED_FORMATS: FileFormat[] = ['pdf', 'txt', 'md'];

export const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB

export function getFileFormatFromExtension(ext?: string | null): FileFormat | null {
  if (!ext) return null;
  const normalized = ext.toLowerCase();
  const map: Record<string, FileFormat> = {
    pdf: 'pdf',
    txt: 'txt',
    text: 'txt',
    md: 'md',
    markdown: 'md',
  };

  return map[normalized] ?? null;
}

export function getFileFormatFromFilename(filename: string): FileFormat | null {
  const parts = filename.split('.');
  if (parts.length < 2) return null;
  const ext = parts[parts.length - 1];
  return getFileFormatFromExtension(ext);
}
