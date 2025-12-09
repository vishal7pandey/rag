import React, { useState } from 'react';

import { useFileUpload } from '@/hooks/useFileUpload';

import { FileDropZone } from './FileDropZone';
import { UploadedFilesList } from './UploadedFilesList';
import styles from './FileUploadZone.module.css';

export const FileUploadZone: React.FC = () => {
  const {
    files,
    isUploading,
    errors,
    handleFileSelection,
    removeFile,
    clearAll,
    cancelUpload,
    retryFile,
  } = useFileUpload();

  const [isDragging, setIsDragging] = useState(false);

  return (
    <div className={styles.container}>
      {errors.size > 0 && (
        <div className={styles.errorSection} role="alert">
          <div className={styles.errorHeader}>
            <span className={styles.errorIcon}>⚠️</span>
            <h4 className={styles.errorTitle}>Upload issues</h4>
          </div>
          <ul className={styles.errorList}>
            {Array.from(errors.entries()).map(([filename, message]) => (
              <li key={filename}>
                <strong>{filename}</strong>: {message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <FileDropZone
        onFilesSelected={handleFileSelection}
        disabled={isUploading}
        isDragging={isDragging}
        onDragStateChange={setIsDragging}
      />

      {isUploading && (
        <div className={styles.actionsRow}>
          <button
            type="button"
            className={styles.cancelButton}
            onClick={cancelUpload}
          >
            Cancel upload
          </button>
        </div>
      )}

      {files.length > 0 && (
        <div className={styles.listSection}>
          <div className={styles.listHeader}>
            <h4 className={styles.listTitle}>
              {files.length} file{files.length !== 1 ? 's' : ''} uploaded
            </h4>
            <button
              type="button"
              className={styles.clearButton}
              onClick={clearAll}
              disabled={isUploading}
              aria-label="Clear all files"
            >
              Clear
            </button>
          </div>

          <UploadedFilesList
            files={files}
            onRemove={removeFile}
            isUploading={isUploading}
            onRetry={retryFile}
          />
        </div>
      )}

      {files.length === 0 && !isUploading && (
        <div className={styles.emptyState}>
          <p className={styles.emptyText}>No files uploaded yet</p>
        </div>
      )}
    </div>
  );
};
