export interface Citation {
  id: number;
  documentId: string;
  documentName: string;
  passage: string;
  chunkId?: string;
  sourceIndex?: number;
  page?: number;
  startChar?: number;
  relevanceScore?: number;
  source?: {
    format: 'pdf' | 'txt' | 'md';
    uploadedAt: string;
  };
}

export interface UsedChunk {
  chunkId: string;
  rank: number;
  similarityScore: number;
  contentPreview: string;
  documentId?: string;
  sourceFile?: string;
  page?: number;
  fullContent?: string;
  uploadedAt?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  usedChunks?: UsedChunk[];
  timestamp: Date;
  isStreaming?: boolean;
  error?: string;
  metadata?: {
    tokenCount?: number;
    responseTimeMs?: number;
    uploadedDocuments?: string[];
    traceId?: string;
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
    traceId?: string;
  };
}

export interface SSEChunk {
  type: 'start' | 'chunk' | 'end' | 'error';
  content?: string;
  conversationId?: string;
  messageId?: string;
  citations?: Citation[];
  usedChunks?: UsedChunk[];
  metadata?: QueryResponse['metadata'];
  error?: string;
}
