import React from 'react';

import { useQuery } from '@/hooks/useQuery';

import { ChatHistory } from './ChatHistory';
import { QueryInput } from './QueryInput';
import styles from './ChatPanel.module.css';

export const ChatPanel: React.FC = () => {
  const { messages, isLoading, error, submitQuery, clearChat } = useQuery();

  return (
    <div className={styles.panel}>
      <ChatHistory messages={messages} />

      {error && (
        <div className={styles.errorBanner} role="alert">
          ⚠️ {error}
        </div>
      )}

      <div className={styles.inputRow}>
        <QueryInput onSubmit={submitQuery} isLoading={isLoading} />
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
  );
};
