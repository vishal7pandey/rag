import React, { useState } from 'react';

import { MainLayout } from './components/Layout/MainLayout';
import { TabNavigation } from './components/Navigation/TabNavigation';
import Ingestion from './pages/Ingestion';
import Insights from './pages/Insights';
import Query from './pages/Query';
import './styles/globals.css';

import styles from './App.module.css';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'ingestion' | 'query' | 'insights'>(
    'query',
  );

  const contentTabs = [
    { id: 'ingestion', label: 'Documents', icon: '📄' },
    { id: 'query', label: 'Chat', icon: '💬' },
    { id: 'insights', label: 'Insights', icon: '📊' },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'ingestion':
        return (
          <div className={styles.tabContent}>
            <Ingestion />
          </div>
        );
      case 'insights':
        return (
          <div className={styles.tabContent}>
            <Insights />
          </div>
        );
      case 'query':
      default:
        return (
          <div className={styles.tabContent}>
            <Query />
          </div>
        );
    }
  };

  return (
    <MainLayout
      activeTab={activeTab}
      onTabChange={setActiveTab}
    >
      <TabNavigation
        tabs={contentTabs}
        activeTab={activeTab}
        onTabChange={(tabId) =>
          setActiveTab(tabId as 'ingestion' | 'query' | 'insights')
        }
      />

      {renderTabContent()}
    </MainLayout>
  );
};

export default App;
