import React from 'react';

import { UploadedFile } from '@/types/upload';
import { UploadService } from '@/services/uploadService';

import { ProgressBar } from './ProgressBar';
import { StatusBadge } from './StatusBadge';
import styles from './UploadedFileItem.module.css';

interface UploadedFileItemProps {
  file: UploadedFile;
  onRemove: () => void;
  canRemove?: boolean;
  onRetry?: () => void;
}

export const UploadedFileItem: React.FC<UploadedFileItemProps> = ({
  file,
  onRemove,
  canRemove = true,
  onRetry,
}) => {
  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
  };

  const getFileIcon = (format: string) => {
    const icons: Record<string, string> = {
      pdf: '📄',
      txt: '📝',
      md: '📋',
    };

    return icons[format] ?? '📎';
  };

  return (
    <div className={styles.row}>
      <div className={styles.colName}>
        <div className={styles.filename}>
          <span className={styles.icon}>{getFileIcon(file.format)}</span>
          <span className={styles.name}>{file.filename}</span>
        </div>

        {file.status === 'uploading' && (
          <ProgressBar progress={file.progress} />
        )}
      </div>

      <div className={styles.colSize}>
        {UploadService.formatFileSize(file.size)}
      </div>

      <div className={styles.colTime}>{formatTime(file.uploadedAt)}</div>

      <div className={styles.colStatus}>
        <StatusBadge status={file.status} message={file.errorMessage} />
      </div>

      <div className={styles.colActions}>
        <button
          type="button"
          className={styles.removeButton}
          onClick={onRemove}
          disabled={!canRemove}
          aria-label={`Remove ${file.filename}`}
          title="Remove file"
        >
          ×
        </button>
        {file.status === 'error' && onRetry && (
          <button
            type="button"
            className={styles.retryButton}
            onClick={onRetry}
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
};
