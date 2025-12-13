import React, { useEffect, useMemo, useRef, useState } from 'react';

import { UsedChunk } from '@/types/query';

import styles from './SourcesPanel.module.css';

interface SourcesPanelProps {
  sources: UsedChunk[];
  isOpen: boolean;
  onToggle: () => void;
  onRequestClose?: () => void;
  focusChunkId?: string | null;
  panelId?: string;
}

const formatPercent = (score: number) => `${Math.round(score * 100)}%`;

const getScoreClass = (score: number) => {
  const pct = score * 100;
  if (pct >= 80) return styles.scoreHigh;
  if (pct >= 50) return styles.scoreMedium;
  return styles.scoreLow;
};

export const SourcesPanel: React.FC<SourcesPanelProps> = ({
  sources,
  isOpen,
  onToggle,
  onRequestClose,
  focusChunkId,
  panelId = 'sources-panel',
}) => {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const isMobileRef = useRef<boolean>(false);

  const computeIsMobile = () => {
    if (typeof window === 'undefined') return false;
    if (typeof window.matchMedia === 'function') {
      return window.matchMedia('(max-width: 768px)').matches;
    }
    return window.innerWidth <= 768;
  };

  const sortedSources = useMemo(
    () => [...sources].sort((a, b) => a.rank - b.rank),
    [sources],
  );

  useEffect(() => {
    if (typeof window === 'undefined') return;
    isMobileRef.current = computeIsMobile();
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    if (!isMobileRef.current) return;

    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        (onRequestClose ?? onToggle)();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onRequestClose, onToggle]);

  useEffect(() => {
    if (!focusChunkId) return;

    setHighlightedId(focusChunkId);

    const el = document.getElementById(`source-${focusChunkId}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    (el as HTMLElement | null)?.focus?.();

    const timer = window.setTimeout(() => setHighlightedId(null), 4500);
    return () => window.clearTimeout(timer);
  }, [focusChunkId]);

  const panelClassName = `${styles.panel} ${isOpen ? styles.open : styles.closed}`;

  return (
    <>
      {isOpen && isMobileRef.current && (
        <div
          className={styles.backdrop}
          onClick={onRequestClose ?? onToggle}
          aria-hidden="true"
        />
      )}

      <aside
        id={panelId}
        className={panelClassName}
        aria-label="Sources panel"
        aria-hidden={!isOpen}
      >
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <h3 className={styles.title}>Sources</h3>
          <span className={styles.count}>{sortedSources.length} used</span>
        </div>

        <button
          type="button"
          className={styles.toggleButton}
          onClick={isOpen ? (onRequestClose ?? onToggle) : onToggle}
          aria-controls={panelId}
          aria-expanded={isOpen}
          aria-label={isOpen ? 'Close sources panel' : 'Open sources panel'}
          title={isOpen ? 'Close' : 'Open'}
        >
          {isOpen ? '✕' : '☰'}
        </button>
      </div>

      {sortedSources.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>📚</div>
          <h4 className={styles.emptyTitle}>No Sources Used</h4>
          <p className={styles.emptyDescription}>
            This answer was generated without using your uploaded documents.
          </p>
        </div>
      ) : (
        <div className={styles.list}>
          {sortedSources.map((s) => {
            const isExpanded = Boolean(expanded[s.chunkId]);
            const showFull = Boolean(s.fullContent) && s.fullContent !== s.contentPreview;
            const docName = s.sourceFile || 'Unknown Document';

            return (
              <div
                key={s.chunkId}
                id={`source-${s.chunkId}`}
                className={`${styles.item} ${
                  highlightedId === s.chunkId ? styles.highlighted : ''
                }`}
                tabIndex={-1}
                role="region"
                aria-label={`Source rank ${s.rank}: ${docName}`}
              >
                <div className={styles.itemHeader}>
                  <div className={styles.leftSection}>
                    <span
                      className={`${styles.rank} ${
                        s.rank === 1 ? styles.rankTop : ''
                      }`}
                    >
                      #{s.rank}
                    </span>

                    <div className={styles.docInfo}>
                      <h4 className={styles.docName} title={docName}>
                        {docName}
                      </h4>
                      <div className={styles.metaLine}>
                        {typeof s.page === 'number' && <span>Page {s.page}</span>}
                        {s.uploadedAt && <span>Uploaded {s.uploadedAt}</span>}
                      </div>
                    </div>
                  </div>

                  <span className={`${styles.score} ${getScoreClass(s.similarityScore)}`}>
                    {formatPercent(s.similarityScore)}
                  </span>
                </div>

                <p className={styles.snippet}>{s.contentPreview}</p>

                {showFull && (
                  <>
                    {isExpanded && (
                      <div className={styles.fullContent}>
                        <p className={styles.snippet}>{s.fullContent}</p>
                      </div>
                    )}

                    <button
                      type="button"
                      className={styles.expandButton}
                      onClick={() =>
                        setExpanded((prev) => ({
                          ...prev,
                          [s.chunkId]: !prev[s.chunkId],
                        }))
                      }
                      aria-label={isExpanded ? 'Collapse source' : 'Expand source'}
                    >
                      {isExpanded ? 'Show less ▲' : 'Read more ▼'}
                    </button>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
      </aside>
    </>
  );
};
