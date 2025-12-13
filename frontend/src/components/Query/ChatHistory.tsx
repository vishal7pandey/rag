import React, { useEffect, useRef } from 'react';

import { ChatMessage as ChatMessageType } from '@/types/query';

import { ChatMessage } from './ChatMessage';
import styles from './ChatHistory.module.css';

interface ChatHistoryProps {
  messages: ChatMessageType[];
  conversationId: string;
  onCitationClick?: (citationId: number) => void;
}

export const ChatHistory: React.FC<ChatHistoryProps> = ({
  messages,
  conversationId,
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
        <p className={styles.inlineHint}>Ask questions about your documents</p>
      </div>
    );
  }

  return (
    <div className={styles.container} ref={containerRef}>
      {messages.map((message) => (
        <ChatMessage
          key={message.id}
          message={message}
          conversationId={conversationId}
          onCitationClick={onCitationClick}
        />
      ))}
    </div>
  );
};
