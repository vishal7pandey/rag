import React from 'react';

import { ChatPanel } from '@/components/Query/ChatPanel';

const Query: React.FC = () => {
  return (
    <section
      aria-labelledby="query-heading"
      style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}
    >
      <header>
        <h2 id="query-heading">Query your knowledge base</h2>
        <p>Ask questions about your uploaded documents and see answers with citations.</p>
      </header>

      <div style={{ flex: 1, minHeight: 0 }}>
        <ChatPanel />
      </div>
    </section>
  );
};

export default Query;
