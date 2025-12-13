import React, { useEffect, useRef, useState } from 'react';

import styles from './QueryInput.module.css';

interface QueryInputProps {
  onSubmit: (query: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
}

export const QueryInput: React.FC<QueryInputProps> = ({
  onSubmit,
  isLoading,
  disabled,
}) => {
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [query, setQuery] = useState('');

  const handleSubmit = () => {
    if (query.trim() && !isLoading && !disabled) {
      onSubmit(query.trim());
      setQuery('');
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      handleSubmit();
    }
  };

  useEffect(() => {
    if (inputRef.current) {
      const el = inputRef.current;
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    }
  }, [query]);

  return (
    <div className={styles.inputWrapper}>
      <textarea
        ref={inputRef}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about your documents..."
        disabled={isLoading || disabled}
        className={styles.input}
        aria-label="Query input"
      />

      <button
        type="button"
        onClick={handleSubmit}
        disabled={!query.trim() || isLoading || disabled}
        className={styles.submitButton}
        title="Ask (Ctrl+Enter)"
        aria-label="Submit query"
      >
        {isLoading ? '⏳' : '→'}
      </button>
    </div>
  );
};
