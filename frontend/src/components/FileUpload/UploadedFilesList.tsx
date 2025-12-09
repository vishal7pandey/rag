import React from 'react';

import { UploadedFile } from '@/types/upload';

import { UploadedFileItem } from './UploadedFileItem';
import styles from './UploadedFilesList.module.css';

interface UploadedFilesListProps {
  files: UploadedFile[];
  onRemove: (fileId: string) => void;
  isUploading?: boolean;
  onRetry?: (fileId: string) => void;
}

export const UploadedFilesList: React.FC<UploadedFilesListProps> = ({
  files,
  onRemove,
  isUploading,
  onRetry,
}) => {
  const sortedFiles = [...files].sort(
    (a, b) => b.uploadedAt.getTime() - a.uploadedAt.getTime(),
  );

  return (
    <div className={styles.list}>
      <div className={styles.header}>
        <div className={styles.colName}>File</div>
        <div className={styles.colSize}>Size</div>
        <div className={styles.colTime}>Uploaded</div>
        <div className={styles.colStatus}>Status</div>
        <div className={styles.colActions} />
      </div>

      {sortedFiles.map((file) => (
        <UploadedFileItem
          key={file.id}
          file={file}
          onRemove={() => onRemove(file.id)}
          onRetry={onRetry ? () => onRetry(file.id) : undefined}
          canRemove={!isUploading}
        />
      ))}
    </div>
  );
};
