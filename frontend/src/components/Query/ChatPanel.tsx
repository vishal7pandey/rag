import React, { useMemo, useRef, useState } from 'react';

import { useQuery } from '@/hooks/useQuery';
import { Citation } from '@/types/query';

import { ChatHistory } from './ChatHistory';
import { QueryInput } from './QueryInput';
import styles from './ChatPanel.module.css';

import { SourcesPanel } from '@/components/Sources/SourcesPanel';

export const ChatPanel: React.FC = () => {
  const { messages, isLoading, error, submitQuery, clearChat, conversationId } =
    useQuery();

  const lastCitationFocusRef = useRef<HTMLElement | null>(null);

  const [focusedChunkId, setFocusedChunkId] = useState<string | null>(null);
  const [isSourcesOpen, setIsSourcesOpen] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    return window.innerWidth >= 769;
  });

  const latestAssistantMessage = useMemo(() => {
    return [...messages].reverse().find((m) => m.role === 'assistant');
  }, [messages]);

  const sources = latestAssistantMessage?.usedChunks ?? [];
  const citations = latestAssistantMessage?.citations ?? [];

  const citationIdToChunkId = useMemo(() => {
    const map = new Map<number, string>();

    for (const c of citations as Citation[]) {
      const direct = c.chunkId;
      if (direct) {
        map.set(c.id, direct);
        continue;
      }

      const rank = c.sourceIndex ?? c.id;
      const match = sources.find((s) => s.rank === rank);
      if (match?.chunkId) {
        map.set(c.id, match.chunkId);
      }
    }

    return map;
  }, [citations, sources]);

  const handleCitationClick = (citationId: number) => {
    const chunkId = citationIdToChunkId.get(citationId);
    if (!chunkId) return;

    lastCitationFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? (document.activeElement as HTMLElement)
        : null;

    setIsSourcesOpen(true);
    setFocusedChunkId(null);
    window.requestAnimationFrame(() => setFocusedChunkId(chunkId));
  };

  const panelId = 'sources-panel';

  const handleCloseSources = () => {
    setIsSourcesOpen(false);
    lastCitationFocusRef.current?.focus?.();
  };

  return (
    <div className={styles.panel}>
      <div className={styles.chatSection}>
        <ChatHistory
          messages={messages}
          conversationId={conversationId}
          onCitationClick={handleCitationClick}
        />

        {error && (
          <div className={styles.errorBanner} role="alert">
            ⚠️ {error}
          </div>
        )}

        <div className={styles.inputRow}>
          <QueryInput onSubmit={submitQuery} isLoading={isLoading} />
          {sources.length > 0 && (
            <button
              type="button"
              className={styles.sourcesToggle}
              onClick={() => setIsSourcesOpen((prev) => !prev)}
              aria-label={isSourcesOpen ? 'Close sources panel' : 'Open sources panel'}
              aria-controls={panelId}
              aria-expanded={isSourcesOpen}
            >
              Sources
            </button>
          )}
          {messages.length > 0 && (
            <button
              type="button"
              onClick={clearChat}
              className={styles.clearButton}
              aria-label="Clear chat history"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {latestAssistantMessage && (
        <SourcesPanel
          sources={sources}
          isOpen={isSourcesOpen}
          onToggle={() => setIsSourcesOpen((prev) => !prev)}
          onRequestClose={handleCloseSources}
          focusChunkId={focusedChunkId}
          panelId={panelId}
        />
      )}
    </div>
  );
};
