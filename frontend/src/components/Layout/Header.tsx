import React from 'react';

import styles from './Header.module.css';

interface HeaderProps {
  onMenuClick?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onMenuClick }) => {
  return (
    <header className={styles.header}>
      <div className={styles.container}>
        {/* Left side: Logo + Title */}
        <div className={styles.leftSection}>
          <button
            className={styles.menuButton}
            onClick={onMenuClick}
            aria-label="Toggle menu"
          >
            ☰
          </button>
          <div className={styles.titleSection}>
            <div className={styles.logo}>🔍</div>
            <h1 className={styles.title}>RAG UI</h1>
          </div>
        </div>

        {/* Right side: Actions */}
        <div className={styles.rightSection}>
          <button className={styles.iconButton} aria-label="Settings">
            ⚙️
          </button>
          <button className={styles.iconButton} aria-label="Help">
            ?
          </button>
        </div>
      </div>
    </header>
  );
};
