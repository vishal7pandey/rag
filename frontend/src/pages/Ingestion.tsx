import React from 'react';

import { FileUploadZone } from '@/components/FileUpload/FileUploadZone';

const Ingestion: React.FC = () => {
  return (
    <section aria-labelledby="ingestion-heading">
      <header>
        <h2 id="ingestion-heading">Upload documents</h2>
        <p>Upload PDF, TXT, or Markdown files to add knowledge to the system.</p>
      </header>

      <FileUploadZone />
    </section>
  );
};

export default Ingestion;
