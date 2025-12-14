import { useCallback, useEffect, useRef, useState } from 'react';

import {
  UploadedFile,
  getFileFormatFromFilename,
} from '@/types/upload';
import uploadService from '@/services/uploadService';
import { apiClient } from '@/services/apiClient';

const STORAGE_KEY = 'rag_uploaded_files';

const createId = (): string => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return (crypto as Crypto).randomUUID();
  }

  return Math.random().toString(36).slice(2);
};

interface StoredUploadedFile
  extends Omit<UploadedFile, 'uploadedAt' | 'originalFile'> {
  uploadedAt: string;
}

export const useFileUpload = () => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [errors, setErrors] = useState<Map<string, string>>(new Map());
  const uploadAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;

      const parsed = JSON.parse(raw) as StoredUploadedFile[];
      const restored = parsed.map<UploadedFile>((file) => ({
        ...file,
        uploadedAt: new Date(file.uploadedAt),
      }));

      setFiles(restored);
    } catch {
      // ignore storage errors
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    try {
      const serializable: StoredUploadedFile[] = files.map((file) => ({
        ...file,
        uploadedAt: file.uploadedAt.toISOString(),
      }));

      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(serializable));
    } catch {
      // ignore storage errors
    }
  }, [files]);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const pollIntervalMs = 1500;
    const maxPollMinutes = 10;
    const maxPollMs = maxPollMinutes * 60 * 1000;

    const tick = async () => {
      const targets = files.filter((f) => f.status === 'processing' && !!f.ingestionId);
      if (targets.length === 0) return;

      await Promise.all(
        targets.map(async (file) => {
          try {
            const startedAt = file.uploadedAt instanceof Date ? file.uploadedAt.getTime() : Date.now();
            if (Date.now() - startedAt > maxPollMs) {
              setFiles((prev) =>
                prev.map((p) =>
                  p.id === file.id
                    ? {
                        ...p,
                        status: 'error',
                        errorMessage: 'Timed out waiting for ingestion to complete.',
                      }
                    : p,
                ),
              );
              return;
            }

            const resp = await apiClient.get(`/ingestion/status/${file.ingestionId}`);
            const data = resp.data as any;
            const statusRaw = String(data?.status ?? '').toLowerCase();

            if (statusRaw === 'completed') {
              setFiles((prev) =>
                prev.map((p) =>
                  p.id === file.id
                    ? {
                        ...p,
                        status: 'success',
                        documentId: data?.document_id ? String(data.document_id) : p.documentId,
                        ingestionId: data?.ingestion_id ? String(data.ingestion_id) : p.ingestionId,
                        errorMessage: undefined,
                      }
                    : p,
                ),
              );
              return;
            }

            if (statusRaw === 'failed') {
              setFiles((prev) =>
                prev.map((p) =>
                  p.id === file.id
                    ? {
                        ...p,
                        status: 'error',
                        errorMessage: data?.error_message ? String(data.error_message) : 'Ingestion failed.',
                      }
                    : p,
                ),
              );
              return;
            }
          } catch {
            // ignore transient polling errors
          }
        }),
      );
    };

    const interval = window.setInterval(() => {
      void tick();
    }, pollIntervalMs);

    return () => window.clearInterval(interval);
  }, [files]);

  const handleFileSelection = useCallback(async (selectedFiles: File[]) => {
    if (!selectedFiles || selectedFiles.length === 0) {
      setErrors(new Map([[
        '__global__',
        'Please select at least one file.',
      ]]));
      return;
    }

    setErrors(new Map());
    setIsUploading(true);

    uploadAbortRef.current?.abort();
    const controller = new AbortController();
    uploadAbortRef.current = controller;

    try {
      const { valid, errors: validationErrors } =
        uploadService.validateFiles(selectedFiles);

      if (validationErrors.size > 0) {
        setErrors(validationErrors);
      }

      if (valid.length === 0) {
        setIsUploading(false);
        return;
      }

      const newFiles: UploadedFile[] = valid.map((file) => {
        const format = getFileFormatFromFilename(file.name) ?? 'txt';

        return {
          id: createId(),
          filename: file.name,
          size: file.size,
          format,
          uploadedAt: new Date(),
          status: 'uploading',
          progress: 0,
          originalFile: file,
        };
      });

      const newFileIds = new Set(newFiles.map((f) => f.id));

      setFiles((prev) => [...prev, ...newFiles]);

      const response = await uploadService.uploadFiles(valid, (_index, progress) => {
        setFiles((prev) =>
          prev.map((file) =>
            newFileIds.has(file.id)
              ? { ...file, progress }
              : file,
          ),
        );
      }, controller.signal);

      const respAny = response as any;

      // Backend currently returns IngestionResponse (snake_case) while the
      // frontend types were originally defined for a camelCase UploadResponse.
      // Support both shapes to avoid UI showing "Failed" on successful 202.
      const isIngestionResponse =
        respAny && typeof respAny === 'object' && 'ingestion_id' in respAny;

      const uploadedFiles = isIngestionResponse
        ? newFiles.map((base) => {
            const ingestionStatus = String(respAny.status ?? '').toLowerCase();
            const normalizedStatus: UploadedFile['status'] =
              ingestionStatus === 'completed'
                ? 'success'
                : ingestionStatus === 'failed'
                  ? 'error'
                  : 'processing';

            return {
              ...base,
              status: normalizedStatus,
              progress: 100,
              documentId: respAny.document_id ? String(respAny.document_id) : undefined,
              ingestionId: respAny.ingestion_id ? String(respAny.ingestion_id) : undefined,
              errorMessage: respAny.error_message ? String(respAny.error_message) : undefined,
            } satisfies UploadedFile;
          })
        : response.files.map((backendFile, index) => {
            const base = newFiles[index] ?? newFiles[newFiles.length - 1];

            return {
              ...base,
              status: backendFile.status === 'success' ? 'success' : 'error',
              progress: 100,
              documentId: backendFile.documentId,
              ingestionId: response.ingestionId,
              errorMessage: backendFile.message,
            } satisfies UploadedFile;
          });

      setFiles((prev) =>
        prev.map((file) => {
          const updated = uploadedFiles.find(
            (uf) => uf.id === file.id,
          );

          return updated ?? file;
        }),
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Upload failed. Please try again.';

      setFiles((prev) =>
        prev.map((file) =>
          file.status === 'uploading'
            ? {
                ...file,
                status: 'error',
                errorMessage: message,
                progress: 0,
              }
            : file,
        ),
      );
    } finally {
      setIsUploading(false);
      uploadAbortRef.current = null;
    }
  }, []);

  const removeFile = useCallback((fileId: string) => {
    setFiles((prev) => prev.filter((file) => file.id !== fileId));
  }, []);

  const clearAll = useCallback(() => {
    setFiles([]);
    setErrors(new Map());
  }, []);

  const cancelUpload = useCallback(() => {
    if (uploadAbortRef.current) {
      uploadAbortRef.current.abort();
    }
  }, []);

  const retryFile = useCallback(async (fileId: string) => {
    const target = files.find((file) => file.id === fileId);
    if (!target || !target.originalFile) return;

    setErrors(new Map());
    setIsUploading(true);

    uploadAbortRef.current?.abort();
    const controller = new AbortController();
    uploadAbortRef.current = controller;

    const fileToRetry = target.originalFile;

    setFiles((prev) =>
      prev.map((file) =>
        file.id === fileId
          ? {
              ...file,
              status: 'uploading',
              progress: 0,
              errorMessage: undefined,
            }
          : file,
      ),
    );

    try {
      const response = await uploadService.uploadFiles(
        [fileToRetry],
        (_index, progress) => {
          setFiles((prev) =>
            prev.map((file) =>
              file.id === fileId
                ? {
                    ...file,
                    progress,
                  }
                : file,
            ),
          );
        },
        controller.signal,
      );

      const respAny = response as any;
      const isIngestionResponse =
        respAny && typeof respAny === 'object' && 'ingestion_id' in respAny;

      const backendFile = isIngestionResponse ? undefined : response.files[0];

      const ingestionStatus = isIngestionResponse
        ? String(respAny.status ?? '').toLowerCase()
        : undefined;

      const normalizedStatus: UploadedFile['status'] = isIngestionResponse
        ? ingestionStatus === 'completed'
          ? 'success'
          : ingestionStatus === 'failed'
            ? 'error'
            : 'processing'
        : backendFile?.status === 'success'
          ? 'success'
          : 'error';

      setFiles((prev) =>
        prev.map((file) =>
          file.id === fileId
            ? {
                ...file,
                status: normalizedStatus,
                progress: 100,
                documentId: isIngestionResponse
                  ? respAny.document_id
                    ? String(respAny.document_id)
                    : undefined
                  : backendFile?.documentId,
                ingestionId: isIngestionResponse
                  ? respAny.ingestion_id
                    ? String(respAny.ingestion_id)
                    : undefined
                  : response.ingestionId,
                errorMessage: isIngestionResponse
                  ? respAny.error_message
                    ? String(respAny.error_message)
                    : undefined
                  : backendFile?.message,
              }
            : file,
        ),
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Upload failed. Please try again.';

      setFiles((prev) =>
        prev.map((file) =>
          file.id === fileId && file.status === 'uploading'
            ? {
                ...file,
                status: 'error',
                errorMessage: message,
                progress: 0,
              }
            : file,
        ),
      );
    } finally {
      setIsUploading(false);
      uploadAbortRef.current = null;
    }
  }, [files]);

  return {
    files,
    isUploading,
    errors,
    handleFileSelection,
    removeFile,
    clearAll,
    cancelUpload,
    retryFile,
  };
};
