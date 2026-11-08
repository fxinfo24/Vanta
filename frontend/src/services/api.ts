/// <reference types="vite/client" />
// API Service for Vanta Frontend
import axios, { AxiosInstance } from 'axios';
import { AnalysisRequest, ApiResponse } from '@/types';

class ApiService {
  private api: AxiosInstance;
  private baseURL: string;

  constructor() {
    // In production (Vercel), set VITE_API_BASE_URL to the live backend base URL
    // (e.g. https://<backend-host>/api) in the Vercel project settings.
    // NOTE: no backend URL is hardcoded here — a hardcoded host previously pointed
    // at a dead Railway deployment and 404'd every call. Deploy the Flask backend
    // (see Dockerfile) first, then set the env var and redeploy the frontend.
    // In development, default to Vite proxy for /api.
    this.baseURL = import.meta.env.VITE_API_BASE_URL || '/api';

    this.api = axios.create({
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Response interceptor for error handling
    this.api.interceptors.response.use(
      (response) => response,
      (error) => Promise.reject(error)
    );
  }

  // NOTE: This frontend currently integrates with the Flask API implemented in
  // `app/web/routes/api.py`.
  // Implemented endpoints:
  // - POST   /api/analyze
  // - GET    /api/tasks
  // - GET    /api/tasks/:id
  // - GET    /api/tasks/:id/status
  // - POST   /api/tasks/:id/cancel
  // - GET    /api/tasks/:id/results
  // - GET    /api/tasks/:id/download
  // - GET    /api/stats/*

  // Task / Analysis
  async createAnalysis(request: AnalysisRequest): Promise<ApiResponse<{ task: any }>> {
    try {
      const payload = {
        platform: request.platform,
        profile_id: request.profileId,
        mode: request.mode || 'deep'
      };
      const response = await this.api.post('/analyze', payload);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async getTask(taskId: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get(`/tasks/${taskId}`);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async listTasks(params?: { platform?: string; status?: string; limit?: number; offset?: number }): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get('/tasks', { params });
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async getTaskStatus(taskId: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get(`/tasks/${taskId}/status`);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async getTaskResults(taskId: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get(`/tasks/${taskId}/results`);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async downloadTaskResults(taskId: number): Promise<Blob> {
    const response = await this.api.get(`/tasks/${taskId}/download`, { responseType: 'blob' });
    return response.data;
  }

  async retryTask(taskId: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.post(`/tasks/${taskId}/retry`);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async cancelTask(taskId: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.post(`/tasks/${taskId}/cancel`);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async getTasks(params?: string): Promise<ApiResponse<any>> {
    try {
      const url = params ? `/tasks?${params}` : '/tasks';
      const response = await this.api.get(url);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async getPlatformDistribution(): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get('/stats/platform-distribution');
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async getCompletionRate(): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get('/stats/completion-rate');
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  // Verification (Product B) — consolidated into the same Flask app
  async createVerificationPost(payload: { platform?: string; profile_id?: string; text: string; author_name?: string; post_url?: string }): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.post('/verification/post', payload);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async createPostFromTask(taskId: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.post(`/verification/post/from-task/${taskId}`);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async verifyTask(taskId: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.post(`/verification/task/${taskId}/run`);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async runVerificationPipeline(payload?: { post_id?: string; limit?: number }): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.post('/verification/pipeline', payload || {});
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async listVerificationPosts(limit?: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get('/verification/posts', { params: { limit: limit || 20 } });
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async listVerificationClaims(limit?: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get('/verification/claims', { params: { limit: limit || 20 } });
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async getVerificationClaim(claimId: string): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get(`/verification/claim/${claimId}`);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async apifyHealth(): Promise<ApiResponse<any>> {
    try { const r = await this.api.get('/apify/health'); return { success: true, data: r.data }; } catch (e) { return this.handleError(e); }
  }
  async apifyRun(payload: any): Promise<ApiResponse<any>> {
    try { const r = await this.api.post('/apify/run', payload); return { success: true, data: r.data }; } catch (e) { return this.handleError(e); }
  }

  async listVerificationResults(limit?: number): Promise<ApiResponse<any>> {
    try {
      const response = await this.api.get('/verification/results', { params: { limit: limit || 20 } });
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  // Error handling
  private handleError(error: any): ApiResponse<never> {
    console.error('API Error:', error);

    const message = error.response?.data?.message ||
      error.response?.data?.error ||
      error.message ||
      'An unexpected error occurred';

    return {
      success: false,
      error: message
    };
  }

  // Utility methods
  // Auth is not implemented in this repository's Flask API.
  // If you deploy publicly, put auth in front of the API or add auth routes.
  isAuthenticated(): boolean {
    return true;
  }
}

// Create and export singleton instance
export const apiService = new ApiService();
export default apiService;