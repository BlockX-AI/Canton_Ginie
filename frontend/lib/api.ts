import axios from "axios";

const BASE_URL = "/api/v1";

export interface GenerateRequest {
  prompt: string;
  canton_environment?: "sandbox" | "devnet" | "mainnet";
  canton_url?: string;
}

export interface GenerateResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed";
  current_step: string;
  progress: number;
  updated_at?: string;
  error_message?: string;
}

export interface JobResult {
  job_id: string;
  status: string;
  contract_id?: string;
  package_id?: string;
  explorer_link?: string;
  generated_code?: string;
  structured_intent?: Record<string, unknown>;
  attempt_number?: number;
  error_message?: string;
  compile_errors?: CompileError[];
}

export interface CompileError {
  file: string;
  line: number;
  column: number;
  message: string;
  error_type: string;
  fixable: boolean;
}

export async function generateContract(req: GenerateRequest): Promise<GenerateResponse> {
  const { data } = await axios.post(`${BASE_URL}/generate`, req);
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const { data } = await axios.get(`${BASE_URL}/status/${jobId}`);
  return data;
}

export async function getJobResult(jobId: string): Promise<JobResult> {
  const { data } = await axios.get(`${BASE_URL}/result/${jobId}`);
  return data;
}

export async function iterateContract(jobId: string, feedback: string, originalCode?: string): Promise<GenerateResponse> {
  const { data } = await axios.post(`${BASE_URL}/iterate/${jobId}`, {
    feedback,
    original_code: originalCode,
  });
  return data;
}

export async function pollUntilComplete(
  jobId: string,
  onProgress: (status: JobStatus) => void,
  intervalMs = 1500
): Promise<JobResult> {
  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const status = await getJobStatus(jobId);
        onProgress(status);

        if (status.status === "complete" || status.status === "failed") {
          try {
            const result = await getJobResult(jobId);
            resolve(result);
          } catch {
            resolve({ job_id: jobId, status: status.status, error_message: status.error_message });
          }
          return;
        }
        setTimeout(poll, intervalMs);
      } catch (err) {
        reject(err);
      }
    };
    poll();
  });
}
