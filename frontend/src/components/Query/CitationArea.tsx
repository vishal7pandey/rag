import React, { useState } from 'react';

import { Citation } from '@/types/query';

import { CitationBadge } from './CitationBadge';
import { CitationModal } from './CitationModal';
import styles from './CitationArea.module.css';

interface CitationAreaProps {
  citations: Citation[];
}

export const CitationArea: React.FC<CitationAreaProps> = ({ citations }) => {
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(
    null,
  );

  if (!citations.length) return null;

  return (
    <>
      <div className={styles.citationArea}>
        <h4 className={styles.heading}>Sources</h4>
        <div className={styles.badges}>
          {citations.map((citation) => (
            <CitationBadge
              key={citation.id}
              citation={citation}
              onClick={() => setSelectedCitation(citation)}
            />
          ))}
        </div>
      </div>

      {selectedCitation && (
        <CitationModal
          citation={selectedCitation}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </>
  );
};
