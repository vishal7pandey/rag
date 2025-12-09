import React, { useState } from 'react';

import { MainLayout } from './components/Layout/MainLayout';
import { TabNavigation } from './components/Navigation/TabNavigation';
import Ingestion from './pages/Ingestion';
import Query from './pages/Query';
import './styles/globals.css';

import styles from './App.module.css';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'ingestion' | 'query'>('query');

  const contentTabs = [
    { id: 'ingestion', label: 'Ingestion', icon: '📄' },
    { id: 'query', label: 'Query', icon: '❓' },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'ingestion':
        return (
          <div className={styles.tabContent}>
            <Ingestion />
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
      // Sidebar has a Settings tab, but the main content currently only
      // differentiates between ingestion and query per Story 017.
      onTabChange={(tab) => setActiveTab(tab as 'ingestion' | 'query')}
    >
      <div className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>
          {activeTab === 'ingestion' ? 'Document Ingestion' : 'Ask Questions'}
        </h1>
        <p className={styles.pageDescription}>
          {activeTab === 'ingestion'
            ? 'Upload and process your documents'
            : 'Query your documents with AI'}
        </p>
      </div>

      <TabNavigation
        tabs={contentTabs}
        activeTab={activeTab}
        onTabChange={(tabId) => setActiveTab(tabId as 'ingestion' | 'query')}
      />

      {renderTabContent()}
    </MainLayout>
  );
};

export default App;
