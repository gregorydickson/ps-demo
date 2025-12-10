import axios, { AxiosError } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add error interceptor for consistent error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      // Server responded with error
      const message = (error.response.data as any)?.detail || error.message;
      throw new Error(message);
    } else if (error.request) {
      // Request made but no response
      throw new Error('No response from server. Please check your connection.');
    } else {
      // Error setting up request
      throw new Error(error.message || 'An unexpected error occurred');
    }
  }
);

// TypeScript types
export interface ContractMetadata {
  filename: string;
  uploaded_at: string;
  parties: string[];
  contract_type?: string;
  effective_date?: string;
}

export interface KeyTerm {
  term: string;
  description: string;
  section?: string;
}

export interface RiskFactor {
  section: string;
  concern: string;
  risk_level: 'low' | 'medium' | 'high';
  recommendation: string;
}

export interface ContractDetails {
  contract_id: string;
  metadata: ContractMetadata;
  key_terms: KeyTerm[];
  risk_score: number;
  risk_factors: RiskFactor[];
  summary?: string;
}

export interface QueryResponse {
  answer: string;
  sources: string[];
  cost: number;
}

export interface ModelCostBreakdown {
  model: string;
  total_cost: number;
  calls: number;
  total_tokens: number;
}

export interface CostAnalytics {
  date: string;
  total_cost: number;
  model_breakdown: ModelCostBreakdown[];
  total_calls: number;
  total_tokens: number;
}

export interface UploadResponse {
  contract_id: string;
  message: string;
}

// API functions
export async function uploadContract(
  file: File,
  onUploadProgress?: (progress: number) => void
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<UploadResponse>(
    '/api/contracts/upload',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onUploadProgress && progressEvent.total) {
          const progress = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onUploadProgress(progress);
        }
      },
    }
  );

  return response.data;
}

export async function queryContract(
  contractId: string,
  query: string
): Promise<QueryResponse> {
  const response = await apiClient.post<QueryResponse>(
    `/api/contracts/${contractId}/query`,
    { query }
  );

  return response.data;
}

export async function getContractDetails(
  contractId: string
): Promise<ContractDetails> {
  const response = await apiClient.get<ContractDetails>(
    `/api/contracts/${contractId}`
  );

  return response.data;
}

export async function getCostAnalytics(date?: string): Promise<CostAnalytics> {
  const params = date ? { date } : {};
  const response = await apiClient.get<CostAnalytics>('/api/analytics/costs', {
    params,
  });

  return response.data;
}
