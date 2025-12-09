import React from 'react';

import styles from './StatusBadge.module.css';

interface StatusBadgeProps {
  status: 'uploading' | 'processing' | 'success' | 'error';
  message?: string;
}

const STATUS_MAP = {
  uploading: { label: 'Uploading', icon: '⏳', variant: 'info' as const },
  processing: { label: 'Processing', icon: '⚙️', variant: 'info' as const },
  success: { label: 'Complete', icon: '✓', variant: 'success' as const },
  error: { label: 'Failed', icon: '✕', variant: 'error' as const },
} as const;

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, message }) => {
  const config = STATUS_MAP[status];

  return (
    <div
      className={`${styles.badge} ${styles[config.variant]}`}
      title={message}
      aria-label={message ?? config.label}
    >
      <span className={styles.icon}>{config.icon}</span>
      <span className={styles.label}>{config.label}</span>
    </div>
  );
};
