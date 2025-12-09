import React from 'react';

import { describe, expect, it } from 'vitest';
import { renderToString } from 'react-dom/server';

import { MainLayout } from '../src/components/Layout/MainLayout';

describe('MainLayout', () => {
  it('renders header and children content', () => {
    const html = renderToString(
      <MainLayout activeTab="query" onTabChange={() => {}}>
        <div>Child content</div>
      </MainLayout>,
    );

    expect(html).toContain('RAG UI');
    expect(html).toContain('Child content');
  });
});
