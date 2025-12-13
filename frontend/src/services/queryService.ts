import {
  QueryRequest,
  QueryResponse,
  SSEChunk,
  ChatMessage,
  UsedChunk,
  Citation,
} from '@/types/query';

export class QueryError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'QueryError';
  }
}

export class QueryService {
  private readonly apiBaseUrl: string;

  constructor(
    apiBaseUrl: string =
      import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api',
  ) {
    this.apiBaseUrl = apiBaseUrl;
  }

  private normalizeCitations(raw: any[]): Citation[] {
    return (raw ?? []).map((c: any, idx: number) => {
      const chunkId = c?.chunk_id ?? c?.chunkId;
      const docId = c?.document_id ?? c?.documentId ?? c?.source?.document_id;
      const name =
        c?.source_file ?? c?.sourceFile ?? c?.documentName ?? c?.source ?? 'Source';
      const passage = c?.preview ?? c?.passage ?? '';
      const score = c?.similarity_score ?? c?.similarityScore;
      const page = c?.page;
      const sourceIndex = c?.source_index ?? c?.sourceIndex ?? c?.rank;

      return {
        id: typeof c?.id === 'number' ? (c.id as number) : idx + 1,
        documentId: docId ? String(docId) : String(idx + 1),
        documentName: String(name),
        passage: String(passage),
        chunkId: chunkId ? String(chunkId) : undefined,
        sourceIndex:
          typeof sourceIndex === 'number' ? (sourceIndex as number) : undefined,
        page: typeof page === 'number' ? (page as number) : undefined,
        relevanceScore:
          typeof score === 'number' ? (score as number) : undefined,
      };
    });
  }

  private normalizeUsedChunks(raw: any[]): UsedChunk[] {
    return (raw ?? []).map((uc: any) => {
      const chunkId = uc?.chunk_id ?? uc?.chunkId;
      const rank = uc?.rank;
      const similarityScore = uc?.similarity_score ?? uc?.similarityScore;
      const contentPreview = uc?.content_preview ?? uc?.contentPreview ?? '';
      const documentId = uc?.document_id ?? uc?.documentId;
      const sourceFile = uc?.source_file ?? uc?.sourceFile;
      const page = uc?.page;
      const fullContent = uc?.full_content ?? uc?.fullContent;
      const uploadedAt = uc?.uploaded_at ?? uc?.uploadedAt;

      return {
        chunkId: String(chunkId ?? ''),
        rank: typeof rank === 'number' ? (rank as number) : 0,
        similarityScore:
          typeof similarityScore === 'number' ? (similarityScore as number) : 0,
        contentPreview: String(contentPreview),
        documentId: documentId ? String(documentId) : undefined,
        sourceFile: sourceFile ? String(sourceFile) : undefined,
        page: typeof page === 'number' ? (page as number) : undefined,
        fullContent: fullContent ? String(fullContent) : undefined,
        uploadedAt: uploadedAt ? String(uploadedAt) : undefined,
      };
    });
  }

  async *streamQuery(
    request: QueryRequest,
    onProgress?: (chunk: SSEChunk) => void,
  ): AsyncGenerator<SSEChunk> {
    try {
      const response = await fetch(`${this.apiBaseUrl}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new QueryError(
          'api_error',
          errorBody?.message || `API error: ${response.status}`,
        );
      }

      const contentType = response.headers.get('content-type') ?? '';
      if (contentType.includes('application/json')) {
        const data = (await response.json()) as any;
        const answer: string = String(data?.answer ?? '');
        const citations = Array.isArray(data?.citations) ? data.citations : [];

        const usedChunks = Array.isArray(data?.used_chunks)
          ? data.used_chunks
          : Array.isArray(data?.usedChunks)
            ? data.usedChunks
            : [];

        const mappedCitations = this.normalizeCitations(citations);
        const mappedUsedChunks = this.normalizeUsedChunks(usedChunks);

        const latencyMs =
          typeof data?.latency_ms === 'number' ? (data.latency_ms as number) : 0;
        const totalTokens =
          typeof data?.metadata?.total_tokens_used === 'number'
            ? (data.metadata.total_tokens_used as number)
            : undefined;

        const startChunk: SSEChunk = {
          type: 'start',
          conversationId: String(data?.conversationId ?? ''),
          messageId: String(data?.messageId ?? ''),
        };

        const contentChunk: SSEChunk = {
          type: 'chunk',
          content: answer,
        };

        const endChunk: SSEChunk = {
          type: 'end',
          citations: mappedCitations,
          usedChunks: mappedUsedChunks,
          metadata: {
            tokenCount: totalTokens ?? 0,
            responseTimeMs: Math.round(latencyMs),
            retrievedChunks: Array.isArray(data?.retrieved_chunks)
              ? data.retrieved_chunks.length
              : 0,
            confidenceScore:
              typeof data?.confidence_score === 'number'
                ? (data.confidence_score as number)
                : undefined,
          },
        };

        for (const chunk of [startChunk, contentChunk, endChunk]) {
          onProgress?.(chunk);
          yield chunk;
        }

        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new QueryError('stream_error', 'Failed to read response stream');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)) as SSEChunk;
              onProgress?.(data);
              yield data;
            } catch (error) {
              console.error('Failed to parse SSE chunk:', line, error);
            }
          }
        }
      }

      if (buffer.startsWith('data: ')) {
        try {
          const data = JSON.parse(buffer.slice(6)) as SSEChunk;
          onProgress?.(data);
          yield data;
        } catch (error) {
          console.error('Failed to parse final SSE chunk:', buffer, error);
        }
      }
    } catch (error) {
      if (error instanceof QueryError) {
        throw error;
      }

      if (error instanceof TypeError) {
        throw new QueryError('network_error', 'Network connection failed');
      }

      throw new QueryError('unknown_error', 'An unknown error occurred');
    }
  }

  async queryStream(
    request: QueryRequest,
    onChunk?: (content: string) => void,
  ): Promise<ChatMessage> {
    const messageId = Math.random().toString(36).slice(2);
    let fullAnswer = '';
    let citations: QueryResponse['citations'] = [];
    let usedChunks: UsedChunk[] = [];
    let metadata: QueryResponse['metadata'] | undefined;
    let hasError = false;
    let errorMessage = '';

    try {
      for await (const chunk of this.streamQuery(request)) {
        if (chunk.type === 'chunk' && chunk.content) {
          fullAnswer += chunk.content;
          onChunk?.(chunk.content);
        } else if (chunk.type === 'end') {
          citations = this.normalizeCitations(chunk.citations ?? []);
          usedChunks = this.normalizeUsedChunks(chunk.usedChunks ?? []);
          metadata = chunk.metadata;
        } else if (chunk.type === 'error') {
          hasError = true;
          errorMessage = chunk.error || 'Stream error';
        }
      }

      if (hasError) {
        throw new QueryError('stream_error', errorMessage);
      }

      const now = new Date();

      return {
        id: messageId,
        role: 'assistant',
        content: fullAnswer,
        citations,
        usedChunks,
        timestamp: now,
        metadata,
      };
    } catch (error) {
      if (error instanceof QueryError) {
        throw error;
      }

      throw new QueryError(
        'unknown_error',
        error instanceof Error ? error.message : 'Unknown error',
      );
    }
  }
}

const queryService = new QueryService();

export default queryService;
