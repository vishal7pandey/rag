import React from 'react';

import styles from './ProgressBar.module.css';

interface ProgressBarProps {
  progress: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ progress }) => {
  const clamped = Math.min(Math.max(progress, 0), 100);

  return (
    <div className={styles.container}>
      <div className={styles.bar}>
        <div className={styles.fill} style={{ width: `${clamped}%` }} />
      </div>
      <span className={styles.text}>{Math.round(clamped)}%</span>
    </div>
  );
};
