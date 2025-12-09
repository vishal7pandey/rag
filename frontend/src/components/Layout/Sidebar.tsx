import React from 'react';

import styles from './Sidebar.module.css';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  activeTab: 'ingestion' | 'query' | 'settings';
  onTabChange: (tab: 'ingestion' | 'query' | 'settings') => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  activeTab,
  onTabChange,
}) => {
  const tabs = [
    { id: 'ingestion', label: 'Ingestion', icon: '📄' },
    { id: 'query', label: 'Query', icon: '❓' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ] as const;

  const handleTabClick = (tab: (typeof tabs)[number]['id']) => {
    onTabChange(tab);
    if (window.innerWidth < 768) onClose();
  };

  return (
    <>
      {isOpen && <div className={styles.overlay} onClick={onClose} />}

      <nav className={`${styles.sidebar} ${isOpen ? styles.open : ''}`}>
        <div className={styles.sidebarContent}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`${styles.navItem} ${
                activeTab === tab.id ? styles.active : ''
              }`}
              onClick={() => handleTabClick(tab.id)}
              aria-current={activeTab === tab.id ? 'page' : undefined}
            >
              <span className={styles.navIcon}>{tab.icon}</span>
              <span className={styles.navLabel}>{tab.label}</span>
            </button>
          ))}
        </div>

        <div className={styles.footer}>
          <p className={styles.version}>v0.1.0</p>
        </div>
      </nav>
    </>
  );
};
