import { describe, expect, it } from 'vitest';

import { UploadService } from '../src/services/uploadService';

describe('UploadService', () => {
  const service = new UploadService();

  describe('validateFiles', () => {
    it('accepts a valid PDF file', () => {
      const file = new File(['content'], 'test.pdf', {
        type: 'application/pdf',
      });

      const { valid, errors } = service.validateFiles([file]);

      expect(valid).toHaveLength(1);
      expect(errors.size).toBe(0);
    });

    it('rejects unsupported format', () => {
      const file = new File(['content'], 'test.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });

      const { valid, errors } = service.validateFiles([file]);

      expect(valid).toHaveLength(0);
      expect(errors.has('test.docx')).toBe(true);
    });
  });

  describe('formatFileSize', () => {
    it('formats bytes to human readable units', () => {
      expect(UploadService.formatFileSize(1024)).toBe('1 KB');
      expect(UploadService.formatFileSize(1024 * 1024)).toBe('1 MB');
    });
  });
});
