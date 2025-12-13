import React from 'react';

import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { QueryInput } from '../src/components/Query/QueryInput';

afterEach(cleanup);

describe('QueryInput', () => {
  it('submits on Ctrl+Enter', async () => {
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} />);

    const input = screen.getByPlaceholderText(/ask a question/i);
    const user = userEvent.setup();

    await user.type(input, 'Test query');
    const button = screen.getByRole('button', { name: /submit query/i });
    await user.click(button);

    expect(onSubmit).toHaveBeenCalledWith('Test query');
  });

  it('disables submit when loading', () => {
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} isLoading />);

    const button = screen.getByRole('button', { name: /submit query/i });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });
});
