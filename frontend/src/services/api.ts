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
    // In dev, always use the Vite proxy. A stray exported
    // VITE_API_BASE_URL (e.g. http://localhost:5000 without /api) would
    // otherwise bypass the proxy and hit a non-existent route, which the
    // browser surfaces as a generic "Network Error".
    this.baseURL = import.meta.env.DEV
      ? '/api'
      : import.meta.env.VITE_API_BASE_URL || '/api';

    this.api = axios.create({
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Attach the JWT (if any) to every request. The backend guards all
    // /api routes (except /health and /auth/*) with a Bearer token.
    this.api.interceptors.request.use((config) => {
      const token = localStorage.getItem('vanta_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Response interceptor: surface errors, but absorb the short window when
    // the backend is being replaced (a deploy swap, or a sleeping free-tier
    // instance waking up). During that window the edge answers without CORS
    // headers, which the browser reports as a blocked request — observed live
    // as a failed sign-in with "No 'Access-Control-Allow-Origin' header".
    //
    // Only requests that are safe to repeat are retried. POST /analyze must
    // never be retried: it spends provider credits and the first attempt may
    // have succeeded. GETs and /auth/* cannot double-charge or double-submit.
    this.api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const config: any = error.config || {};
        const status = error.response?.status;
        const transient = !error.response || [502, 503, 504].includes(status);
        const method = String(config.method || 'get').toLowerCase();
        const safeToRepeat = ['get', 'head'].includes(method) || /\/auth\//.test(String(config.url || ''));
        const attempt = config.__retries || 0;

        if (transient && safeToRepeat && attempt < 3) {
          config.__retries = attempt + 1;
          await new Promise((resolve) => setTimeout(resolve, 2000 * config.__retries));
          return this.api.request(config);
        }

        // A rejected token is a logout, not a data error. Clearing it here (and
        // telling the app) sends the user to sign-in; a wrong password on the
        // login form must stay a message on the form, so that route is exempt.
        if (status === 401 && !/\/auth\/(login|register)/.test(String(config.url || ''))) {
          localStorage.removeItem('vanta_token');
          window.dispatchEvent(new Event('vanta:auth-expired'));
        }
        return Promise.reject(error);
      }
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
      // Omit mode unless the caller chose one: the backend applies the
      // user's saved default mode (Settings) when it's absent.
      const payload: Record<string, unknown> = {
        platform: request.platform,
        profile_id: request.profileId,
      };
      if (request.mode) payload.mode = request.mode;
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

  async downloadTaskResults(taskId: number, format?: string): Promise<Blob> {
    // Fetches through the authenticated client (Bearer header attached by
    // the request interceptor). A bare window.open() to /api/... cannot
    // send the token and is rejected by the auth guard with a 401.
    const response = await this.api.get(`/tasks/${taskId}/download`, {
      params: format ? { format } : undefined,
      responseType: 'blob',
    });
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

  // Auth
  async register(email: string, password: string, username?: string): Promise<ApiResponse<any>> {
    try {
      const r = await this.api.post('/auth/register', { email, password, username });
      return { success: true, data: r.data };
    } catch (e) { return this.handleError(e); }
  }

  async login(email: string, password: string): Promise<ApiResponse<any>> {
    try {
      const r = await this.api.post('/auth/login', { email, password });
      return { success: true, data: r.data };
    } catch (e) { return this.handleError(e); }
  }

  async me(): Promise<ApiResponse<any>> {
    try {
      const r = await this.api.get('/auth/me');
      return { success: true, data: r.data };
    } catch (e) { return this.handleError(e); }
  }

  // Public: request a one-time reset link. The response is intentionally the
  // same whether or not the address has an account.
  async forgotPassword(email: string): Promise<ApiResponse<any>> {
    try {
      const r = await this.api.post('/auth/forgot-password', { email });
      return { success: true, data: r.data };
    } catch (e) { return this.handleError(e); }
  }

  // Public: redeem the token from the emailed link.
  async resetPassword(token: string, new_password: string): Promise<ApiResponse<any>> {
    try {
      const r = await this.api.post('/auth/reset-password', { token, new_password });
      return { success: true, data: r.data };
    } catch (e) { return this.handleError(e); }
  }

  async changePassword(current_password: string, new_password: string): Promise<ApiResponse<any>> {
    try {
      const r = await this.api.post('/auth/change-password', { current_password, new_password });
      return { success: true, data: r.data };
    } catch (e) { return this.handleError(e); }
  }

  // Last observed data-provider balance and the credit cost of a run.
  async getProviderUsage(): Promise<ApiResponse<any>> {
    try {
      const r = await this.api.get('/provider/usage');
      return { success: true, data: r.data };
    } catch (e) { return this.handleError(e); }
  }

  // Settings + BYOK. Key material is write-only: responses carry only
  // per-provider status (configured / source / masked hint).
  async getSettings(): Promise<ApiResponse<any>> {
    try {
      const r = await this.api.get('/settings');
      return { success: true, data: r.data };
    } catch (e) { return this.handleError(e); }
  }

  async saveSettings(payload: any): Promise<ApiResponse<any>> {
    try {
      const r = await this.api.put('/settings', payload);
      return { success: true, data: r.data };
    } catch (e) { return this.handleError(e); }
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
  isAuthenticated(): boolean {
    return !!localStorage.getItem('vanta_token');
  }
}

// Create and export singleton instance
export const apiService = new ApiService();
export default apiService;