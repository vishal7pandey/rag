import React, { useEffect, useRef } from 'react';

import { ChatMessage as ChatMessageType } from '@/types/query';

import { ChatMessage } from './ChatMessage';
import styles from './ChatHistory.module.css';

interface ChatHistoryProps {
  messages: ChatMessageType[];
  onCitationClick?: (citationId: number) => void;
}

export const ChatHistory: React.FC<ChatHistoryProps> = ({
  messages,
  onCitationClick,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.icon}>💬</div>
        <h2 className={styles.title}>Start a conversation</h2>
        <p className={styles.description}>
          Ask questions about your uploaded documents.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.container} ref={containerRef}>
      {messages.map((message) => (
        <ChatMessage
          key={message.id}
          message={message}
          onCitationClick={onCitationClick}
        />
      ))}
    </div>
  );
};
