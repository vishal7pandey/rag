import React from 'react';

import { FileUploadZone } from '@/components/FileUpload/FileUploadZone';

const Ingestion: React.FC = () => {
  return (
    <section>
      <p>Upload PDF, TXT, or Markdown (max 100 MB each)</p>
      <FileUploadZone />
    </section>
  );
};

export default Ingestion;
