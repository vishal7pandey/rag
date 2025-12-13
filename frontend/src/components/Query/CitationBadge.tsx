import React, { useState } from 'react';

import { Citation } from '@/types/query';

import styles from './CitationBadge.module.css';

interface CitationBadgeProps {
  citation: Citation;
  onClick: () => void;
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({
  citation,
  onClick,
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  const truncatePassage = (passage: string, maxLen = 100) =>
    passage.length > maxLen ? `${passage.slice(0, maxLen)}...` : passage;

  return (
    <div
      className={styles.badgeWrapper}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <button
        type="button"
        className={styles.badge}
        onClick={onClick}
        aria-label={`Citation ${citation.id}: ${citation.documentName}`}
        title={`Click to view full citation from ${citation.documentName}`}
      >
        [{citation.id}]
      </button>

      {showTooltip && (
        <div className={styles.tooltip} role="tooltip">
          <div className={styles.tooltipContent}>
            <h5 className={styles.tooltipTitle}>{citation.documentName}</h5>
            <p className={styles.tooltipPassage}>
              {truncatePassage(citation.passage)}
            </p>
            {citation.relevanceScore && (
              <div className={styles.tooltipScore}>
                Relevance: {(citation.relevanceScore * 100).toFixed(0)}%
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
