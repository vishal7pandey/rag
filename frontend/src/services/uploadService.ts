import axios, { AxiosProgressEvent } from 'axios';

import { apiClient } from './apiClient';
import {
  UploadResponse,
  SUPPORTED_FORMATS,
  MAX_FILE_SIZE,
  getFileFormatFromExtension,
} from '@/types/upload';

export class UploadError extends Error {
  constructor(
    public code: string,
    message: string,
    public filename?: string,
  ) {
    super(message);
    this.name = 'UploadError';
  }
}

export class UploadService {
  constructor(private readonly client = apiClient) {}

  validateFiles(files: File[]): { valid: File[]; errors: Map<string, string> } {
    const valid: File[] = [];
    const errors = new Map<string, string>();

    for (const file of files) {
      const ext = file.name.split('.').pop();
      const format = getFileFormatFromExtension(ext);

      if (!format) {
        errors.set(
          file.name,
          `Unsupported format. Supported: ${SUPPORTED_FORMATS.join(', ')}`,
        );
        continue;
      }

      if (file.size > MAX_FILE_SIZE) {
        const maxSizeMB = Math.round(MAX_FILE_SIZE / (1024 * 1024));
        errors.set(file.name, `File too large. Max: ${maxSizeMB} MB`);
        continue;
      }

      valid.push(file);
    }

    return { valid, errors };
  }

  async uploadFiles(
    files: File[],
    onProgress?: (fileIndex: number, progress: number) => void,
    signal?: AbortSignal,
  ): Promise<UploadResponse> {
    if (files.length === 0) {
      throw new UploadError('empty_files', 'No files to upload');
    }

    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));

    try {
      const response = await this.client.post<UploadResponse>(
        '/ingestion/upload',
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (event: AxiosProgressEvent) => {
            if (event.total && onProgress) {
              const progress = Math.round((event.loaded / event.total) * 100);
              onProgress(0, progress);
            }
          },
          signal,
          timeout: 300000,
        },
      );

      return response.data;
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        if (error.code === 'ERR_CANCELED') {
          throw new UploadError('canceled', 'Upload cancelled by user.');
        }

        const statusCode = error.response?.status;
        const data = error.response?.data as any;

        if (statusCode === 400) {
          throw new UploadError(
            'unsupported_format',
            data?.error?.message || 'Unsupported file format',
          );
        }

        if (statusCode === 413) {
          throw new UploadError('file_too_large', 'File size exceeds limit');
        }

        if (statusCode === 500) {
          throw new UploadError(
            'server_error',
            'Server error. Please try again later.',
          );
        }

        throw new UploadError('network_error', error.message);
      }

      throw new UploadError('unknown_error', 'An unknown error occurred');
    }
  }

  static formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const value = bytes / Math.pow(k, i);
    const rounded = Math.round(value * 100) / 100;
    return `${rounded} ${sizes[i]}`;
  }
}

const uploadService = new UploadService();

export default uploadService;
