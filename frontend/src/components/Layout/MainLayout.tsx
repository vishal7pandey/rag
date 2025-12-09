import React, { useState } from 'react';

import { Header } from './Header';
import { Sidebar } from './Sidebar';
import styles from './MainLayout.module.css';

interface MainLayoutProps {
  activeTab: 'ingestion' | 'query' | 'settings';
  onTabChange: (tab: 'ingestion' | 'query' | 'settings') => void;
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  activeTab,
  onTabChange,
  children,
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className={styles.container}>
      <Header onMenuClick={() => setSidebarOpen(!sidebarOpen)} />

      <div className={styles.main}>
        <Sidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          activeTab={activeTab}
          onTabChange={onTabChange}
        />

        <main className={styles.content}>{children}</main>
      </div>
    </div>
  );
};
