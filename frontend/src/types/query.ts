export interface Citation {
  id: number;
  documentId: string;
  documentName: string;
  passage: string;
  startChar?: number;
  relevanceScore?: number;
  source?: {
    format: 'pdf' | 'txt' | 'md';
    uploadedAt: string;
  };
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
  isStreaming?: boolean;
  error?: string;
  metadata?: {
    tokenCount?: number;
    responseTimeMs?: number;
    uploadedDocuments?: string[];
  };
}

export interface QueryRequest {
  query: string;
  conversationId: string;
  documentIds?: string[];
  maxTokens?: number;
  temperature?: number;
}

export interface QueryResponse {
  conversationId: string;
  messageId: string;
  answer: string;
  citations: Citation[];
  metadata: {
    tokenCount: number;
    responseTimeMs: number;
    retrievedChunks: number;
    confidenceScore?: number;
  };
}

export interface SSEChunk {
  type: 'start' | 'chunk' | 'end' | 'error';
  content?: string;
  conversationId?: string;
  messageId?: string;
  citations?: Citation[];
  metadata?: QueryResponse['metadata'];
  error?: string;
}
