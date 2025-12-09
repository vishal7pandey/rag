import React from 'react';

import { describe, expect, it } from 'vitest';
import { renderToString } from 'react-dom/server';

import { TabNavigation } from '../src/components/Navigation/TabNavigation';

describe('TabNavigation', () => {
  it('renders tabs and marks the active tab via aria-selected', () => {
    const tabs = [
      { id: 'ingestion', label: 'Ingestion' },
      { id: 'query', label: 'Query' },
    ];

    const html = renderToString(
      <TabNavigation tabs={tabs} activeTab="query" onTabChange={() => {}} />,
    );

    expect(html).toContain('Ingestion');
    expect(html).toContain('Query');
    expect(html).toContain('aria-selected="true"');
  });
});
