import React from 'react';

import { ChatPanel } from '@/components/Query/ChatPanel';

const Query: React.FC = () => {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ChatPanel />
      </div>
    </section>
  );
};

export default Query;
