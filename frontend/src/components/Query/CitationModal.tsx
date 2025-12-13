import React from 'react';

import { Citation } from '@/types/query';

import styles from './CitationModal.module.css';

interface CitationModalProps {
  citation: Citation;
  onClose: () => void;
}

export const CitationModal: React.FC<CitationModalProps> = ({
  citation,
  onClose,
}) => {
  return (
    <div className={styles.backdrop} role="dialog" aria-modal="true">
      <div className={styles.modal}>
        <header className={styles.header}>
          <h3 className={styles.title}>Source details</h3>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label="Close citation details"
          >
            ×
          </button>
        </header>

        <div className={styles.body}>
          <div className={styles.field}>
            <span className={styles.label}>Document</span>
            <span className={styles.value}>{citation.documentName}</span>
          </div>

          <div className={styles.field}>
            <span className={styles.label}>Passage</span>
            <p className={styles.passage}>{citation.passage}</p>
          </div>

          {citation.relevanceScore != null && (
            <div className={styles.field}>
              <span className={styles.label}>Relevance</span>
              <span className={styles.value}>
                {(citation.relevanceScore * 100).toFixed(0)}%
              </span>
            </div>
          )}
        </div>

        <footer className={styles.footer}>
          <button
            type="button"
            className={styles.closeFooterButton}
            onClick={onClose}
          >
            Close
          </button>
        </footer>
      </div>
    </div>
  );
};
