import { FeedbackRequest, FeedbackResponse } from '@/types/feedback';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api';

export const submitFeedback = async (
  request: FeedbackRequest,
): Promise<FeedbackResponse> => {
  const response = await fetch(`${apiBaseUrl}/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      conversationId: request.conversationId,
      messageId: request.messageId,
      traceId: request.traceId,
      thumbsUp: request.thumbsUp,
      rating: request.rating,
      comment: request.comment,
      categories: request.categories,
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.message === 'string'
        ? body.message
        : `Failed to submit feedback (${response.status})`;
    throw new Error(message);
  }

  return (await response.json()) as FeedbackResponse;
};
