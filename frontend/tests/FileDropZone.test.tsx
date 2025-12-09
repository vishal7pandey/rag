import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { FileDropZone } from '../src/components/FileUpload/FileDropZone';

describe('FileDropZone', () => {
  it('renders label and button role', () => {
    render(<FileDropZone onFilesSelected={vi.fn()} />);

    const button = screen.getByRole('button', {
      name: /upload files/i,
    });

    expect(button).toBeTruthy();
    expect(screen.getByText(/drop files here or click to browse/i)).toBeTruthy();
  });

  it('accepts files from file input', async () => {
    const onFilesSelected = vi.fn();
    const user = userEvent.setup();

    const { container } = render(
      <FileDropZone onFilesSelected={onFilesSelected} />,
    );

    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(['content'], 'test.pdf', {
      type: 'application/pdf',
    });

    await user.upload(input, file);

    expect(onFilesSelected).toHaveBeenCalledWith([file]);
  });

});
