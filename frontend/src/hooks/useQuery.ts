import { useCallback, useEffect, useRef, useState } from 'react';

import { ChatMessage } from '@/types/query';
import queryService from '@/services/queryService';

const STORAGE_KEY = 'rag_chat_history';

const createId = (): string => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return (crypto as Crypto).randomUUID();
  }

  return Math.random().toString(36).slice(2);
};

interface StoredChatMessage extends Omit<ChatMessage, 'timestamp'> {
  timestamp: string;
}

interface StoredChatState {
  conversationId: string;
  messages: StoredChatMessage[];
}

export const useQuery = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const conversationIdRef = useRef<string>(createId());

  useEffect(() => {
    if (typeof window === 'undefined') return;

    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;

      const parsed = JSON.parse(raw) as StoredChatState;
      const restoredMessages: ChatMessage[] = parsed.messages.map(
        (msg) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        }),
      );

      setMessages(restoredMessages);
      if (parsed.conversationId) {
        conversationIdRef.current = parsed.conversationId;
      }
    } catch {
      // ignore storage errors
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    try {
      const stored: StoredChatState = {
        conversationId: conversationIdRef.current,
        messages: messages.map<StoredChatMessage>((msg) => ({
          ...msg,
          timestamp: msg.timestamp.toISOString(),
        })),
      };

      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
    } catch {
      // ignore storage errors
    }
  }, [messages]);

  const submitQuery = useCallback(async (queryText: string) => {
    const trimmed = queryText.trim();
    if (!trimmed) return;

    setError(null);
    setIsLoading(true);

    const userMessage: ChatMessage = {
      id: createId(),
      role: 'user',
      content: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);

    const assistantId = createId();
    const assistantPlaceholder: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, assistantPlaceholder]);

    try {
      const response = await queryService.queryStream(
        {
          query: trimmed,
          conversationId: conversationIdRef.current,
        },
        (chunk) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + chunk }
                : msg,
            ),
          );
        },
      );

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? {
                ...msg,
                content: response.content,
                citations: response.citations,
                usedChunks: response.usedChunks,
                metadata: response.metadata,
                isStreaming: false,
              }
            : msg,
        ),
      );
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : 'Failed to get response';
      setError(errorMsg);

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? { ...msg, isStreaming: false, error: errorMsg }
            : msg,
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
    setError(null);
    conversationIdRef.current = createId();
  }, []);

  return {
    messages,
    isLoading,
    error,
    submitQuery,
    clearChat,
  };
};
