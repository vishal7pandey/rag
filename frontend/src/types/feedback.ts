export interface FeedbackRequest {
  conversationId: string;
  messageId: string;
  traceId: string;
  thumbsUp?: boolean;
  rating?: number;
  comment?: string;
  categories?: string[];
}

export interface FeedbackResponse {
  id: string;
  status: string;
  createdAt?: string;
}
