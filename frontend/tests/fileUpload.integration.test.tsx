import React from 'react';

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { FileUploadZone } from '../src/components/FileUpload/FileUploadZone';

vi.mock('@/services/uploadService', async () => {
  const actual = await vi.importActual<
    typeof import('../src/services/uploadService')
  >('../src/services/uploadService');

  return {
    ...actual,
    default: {
      ...actual.default,
      validateFiles: vi.fn((files: File[]) => ({
        valid: files,
        errors: new Map(),
      })),
      uploadFiles: vi.fn(() =>
        Promise.resolve({
          ingestionId: 'test-123',
          files: [
            {
              documentId: 'doc-123',
              filename: 'test.pdf',
              size: 1024,
              uploadedAt: new Date().toISOString(),
              status: 'success' as const,
              message: undefined,
            },
          ],
        }),
      ),
    },
  };
});

describe('FileUploadZone integration', () => {
  it('handles a complete upload flow via file input', async () => {
    const user = userEvent.setup();
    const { container } = render(<FileUploadZone />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['content'], 'test.pdf', {
      type: 'application/pdf',
    });

    await user.upload(input, file);

    await waitFor(() => {
      expect(screen.getByText(/test.pdf/)).toBeTruthy();
      expect(screen.getByText(/complete/i)).toBeTruthy();
    });
  });
});
