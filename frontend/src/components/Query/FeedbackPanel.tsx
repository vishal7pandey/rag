import React, { useMemo, useState } from 'react';

import { submitFeedback } from '@/services/feedbackService';

import styles from './FeedbackPanel.module.css';

interface FeedbackPanelProps {
  conversationId: string;
  messageId: string;
  traceId: string;
}

export const FeedbackPanel: React.FC<FeedbackPanelProps> = ({
  conversationId,
  messageId,
  traceId,
}) => {
  const [thumbsUp, setThumbsUp] = useState<boolean | undefined>(undefined);
  const [rating, setRating] = useState<number | undefined>(undefined);
  const [showDetails, setShowDetails] = useState(false);
  const [comment, setComment] = useState('');
  const [categories, setCategories] = useState<string[]>([]);
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>(
    'idle',
  );

  const isValid = useMemo(() => {
    return (
      typeof thumbsUp === 'boolean' ||
      typeof rating === 'number' ||
      comment.trim().length > 0 ||
      categories.length > 0
    );
  }, [thumbsUp, rating, comment, categories.length]);

  const handleSubmit = async (payload: {
    thumbsUp?: boolean;
    rating?: number;
    comment?: string;
    categories?: string[];
  }) => {
    setStatus('submitting');
    try {
      await submitFeedback({
        conversationId,
        messageId,
        traceId,
        thumbsUp: payload.thumbsUp,
        rating: payload.rating,
        comment: payload.comment,
        categories: payload.categories,
      });
      setStatus('success');
      window.setTimeout(() => setStatus('idle'), 2000);
    } catch {
      setStatus('error');
      window.setTimeout(() => setStatus('idle'), 2500);
    }
  };

  const handleQuick = async (value: boolean) => {
    setThumbsUp(value);
    await handleSubmit({ thumbsUp: value, rating, categories });
  };

  const toggleCategory = (cat: string) => {
    setCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat],
    );
  };

  return (
    <div className={styles.panel} aria-label="Feedback panel">
      <p className={styles.prompt}>Was this helpful?</p>

      <div className={styles.actions}>
        <button
          type="button"
          className={`${styles.button} ${thumbsUp === true ? styles.active : ''}`}
          onClick={() => void handleQuick(true)}
          aria-label="Helpful"
        >
          👍
        </button>

        <button
          type="button"
          className={`${styles.button} ${thumbsUp === false ? styles.active : ''}`}
          onClick={() => void handleQuick(false)}
          aria-label="Not helpful"
        >
          👎
        </button>

        <div className={styles.stars} aria-label="Rating">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              className={`${styles.star} ${
                typeof rating === 'number' && rating >= star ? styles.filled : ''
              }`}
              onClick={() => setRating(star)}
              aria-label={`${star} stars`}
            >
              ⭐
            </button>
          ))}
        </div>
      </div>

      {status !== 'idle' && (
        <div
          className={`${styles.status} ${
            status === 'success'
              ? styles.success
              : status === 'error'
                ? styles.error
                : ''
          }`}
          role={status === 'error' ? 'alert' : undefined}
        >
          {status === 'submitting'
            ? 'Sending…'
            : status === 'success'
              ? 'Thanks for your feedback.'
              : 'Could not send feedback.'}
        </div>
      )}

      <button
        type="button"
        className={styles.detailsToggle}
        onClick={() => setShowDetails((prev) => !prev)}
        aria-expanded={showDetails}
      >
        {showDetails ? 'Hide details' : 'More details'}
      </button>

      {showDetails && (
        <div className={styles.details}>
          <div className={styles.categories} aria-label="Feedback categories">
            {['accurate', 'irrelevant', 'incomplete', 'hallucinated', 'unclear'].map(
              (cat) => (
                <label key={cat} className={styles.categoryLabel}>
                  <input
                    type="checkbox"
                    checked={categories.includes(cat)}
                    onChange={() => toggleCategory(cat)}
                  />
                  {cat}
                </label>
              ),
            )}
          </div>

          <textarea
            className={styles.comment}
            placeholder="Any other thoughts? (optional, max 500 chars)"
            value={comment}
            onChange={(e) => setComment(e.target.value.slice(0, 500))}
            rows={3}
          />

          <div className={styles.submitRow}>
            <button
              type="button"
              className={styles.submit}
              onClick={() =>
                void handleSubmit({
                  thumbsUp,
                  rating,
                  comment: comment.trim(),
                  categories,
                })
              }
              disabled={status === 'submitting' || !isValid}
            >
              Submit
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
