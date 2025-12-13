import React from 'react';

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ChatPanel } from '../src/components/Query/ChatPanel';

vi.mock('@/services/queryService', async () => {
  const actual = await vi.importActual<
    typeof import('../src/services/queryService')
  >('../src/services/queryService');

  return {
    ...actual,
    default: {
      ...actual.default,
      queryStream: vi.fn(() =>
        Promise.resolve({
          id: 'assistant-1',
          role: 'assistant' as const,
          content: 'The answer',
          citations: [
            {
              id: 1,
              documentId: 'doc-1',
              documentName: 'Report.pdf',
              passage: 'Sample text',
            },
          ],
          timestamp: new Date(),
          metadata: {
            tokenCount: 10,
            responseTimeMs: 500,
            retrievedChunks: 1,
          },
        }),
      ),
    },
  };
});

describe('ChatPanel integration', () => {
  it('displays user message and assistant response with citation', async () => {
    const user = userEvent.setup();
    render(<ChatPanel />);

    const input = screen.getByPlaceholderText(/ask a question/i);
    await user.type(input, 'What is X?');
    const button = screen.getByRole('button', { name: /submit query/i });
    await user.click(button);

    // User message appears
    expect(screen.getByText('What is X?')).toBeTruthy();

    // Assistant response appears
    await waitFor(() => {
      expect(screen.getByText(/the answer/i)).toBeTruthy();
    });

    // Citation badge appears
    await waitFor(() => {
      expect(screen.getByText('[1]')).toBeTruthy();
    });
  });
});
