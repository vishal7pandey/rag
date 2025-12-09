import { useCallback, useEffect, useRef, useState } from 'react';

import {
  UploadedFile,
  getFileFormatFromFilename,
} from '@/types/upload';
import uploadService from '@/services/uploadService';

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

      const uploadedFiles = response.files.map((backendFile, index) => {
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

      const backendFile = response.files[0];

      setFiles((prev) =>
        prev.map((file) =>
          file.id === fileId
            ? {
                ...file,
                status:
                  backendFile.status === 'success' ? 'success' : 'error',
                progress: 100,
                documentId: backendFile.documentId,
                ingestionId: response.ingestionId,
                errorMessage: backendFile.message,
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
