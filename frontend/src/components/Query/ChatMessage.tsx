import React from 'react';

import { ChatMessage as ChatMessageType } from '@/types/query';

import { CitationArea } from './CitationArea';
import { FeedbackPanel } from './FeedbackPanel';
import { MarkdownRenderer } from './MarkdownRenderer';
import styles from './ChatMessage.module.css';

interface ChatMessageProps {
  message: ChatMessageType;
  conversationId: string;
  onCitationClick?: (citationId: number) => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  conversationId,
  onCitationClick,
}) => {
  const formatTime = (date: Date) =>
    date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div
      className={`${styles.message} ${styles[message.role]}`}
      role={message.role === 'user' ? 'article' : 'region'}
      aria-label={`${message.role} message at ${formatTime(message.timestamp)}`}
    >
      <div className={styles.content}>
        {message.role === 'user' ? (
          <p className={styles.text}>{message.content}</p>
        ) : (
          <>
            {message.isStreaming && (
              <div className={styles.loadingSpinner} aria-label="Thinking...">
                <div className={styles.dot} />
                <div className={styles.dot} />
                <div className={styles.dot} />
              </div>
            )}

            {message.error ? (
              <p className={styles.error}>Error: {message.error}</p>
            ) : (
              <MarkdownRenderer content={message.content} />
            )}

            {message.citations && message.citations.length > 0 && (
              <CitationArea citations={message.citations} onCitationClick={onCitationClick} />
            )}

            {message.metadata && (
              <div className={styles.metadata}>
                {typeof message.metadata.tokenCount === 'number' && (
                  <span className={styles.tokenCount}>
                    {message.metadata.tokenCount} tokens
                  </span>
                )}
                {typeof message.metadata.responseTimeMs === 'number' && (
                  <span className={styles.responseTime}>
                    {(message.metadata.responseTimeMs / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
            )}

            {message.isStreaming !== true &&
              message.error == null &&
              typeof message.metadata?.traceId === 'string' &&
              message.metadata.traceId.length > 0 && (
                <FeedbackPanel
                  conversationId={conversationId}
                  messageId={message.id}
                  traceId={message.metadata.traceId}
                />
              )}
          </>
        )}
      </div>

      <div className={styles.timestamp}>{formatTime(message.timestamp)}</div>
    </div>
  );
};
