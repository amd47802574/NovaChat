export interface DocumentItem {
  filename: string;
  file_type: string;
  chunk_count: number;
}

export interface UploadStep {
  key: string;
  label: string;
  percent: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  message: string;
}

export interface UploadJob {
  job_id: string;
  status: 'running' | 'completed' | 'failed';
  message: string;
  steps: UploadStep[];
}
