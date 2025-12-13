import React, { useMemo } from 'react';

import DOMPurify from 'dompurify';
import markdownIt from 'markdown-it';

import styles from './MarkdownRenderer.module.css';

const md = markdownIt({
  html: false,
  breaks: true,
  linkify: false,
});

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  const html = useMemo(() => {
    try {
      const raw = md.render(content);
      return DOMPurify.sanitize(raw, {
        ALLOWED_TAGS: [
          'p',
          'br',
          'strong',
          'em',
          'u',
          'code',
          'pre',
          'ul',
          'ol',
          'li',
          'blockquote',
          'a',
          'h1',
          'h2',
          'h3',
          'h4',
          'h5',
          'h6',
        ],
        ALLOWED_ATTR: ['href', 'title', 'target', 'rel'],
      });
    } catch {
      return DOMPurify.sanitize(content);
    }
  }, [content]);

  return (
    <div
      className={styles.markdown}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};
