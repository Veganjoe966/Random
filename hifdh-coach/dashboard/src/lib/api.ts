/**
 * API client for Hifdh Coach backend.
 * Handles authentication, tenant context, and error handling.
 */

import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        "Content-Type": "application/json",
      },
    });

    // Attach JWT to every request
    this.client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
      if (typeof window !== "undefined") {
        const token = localStorage.getItem("access_token");
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
      return config;
    });

    // Handle 401 → refresh token
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401) {
          const refreshToken = localStorage.getItem("refresh_token");
          if (refreshToken) {
            try {
              const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
                refresh_token: refreshToken,
              });
              localStorage.setItem("access_token", response.data.access_token);
              localStorage.setItem("refresh_token", response.data.refresh_token);
              // Retry original request
              error.config.headers.Authorization = `Bearer ${response.data.access_token}`;
              return this.client.request(error.config);
            } catch {
              localStorage.removeItem("access_token");
              localStorage.removeItem("refresh_token");
              window.location.href = "/auth/login";
            }
          }
        }
        return Promise.reject(error);
      }
    );
  }

  // ── Auth ───────────────────────────────────────────────────────────
  async login(email: string, password: string) {
    const { data } = await this.client.post("/auth/login", { email, password });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    return data;
  }

  async register(payload: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    tenant_slug?: string;
  }) {
    const { data } = await this.client.post("/auth/register", payload);
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    return data;
  }

  async getMe() {
    const { data } = await this.client.get("/auth/me");
    return data;
  }

  // ── Recitations ───────────────────────────────────────────────────
  async uploadRecitation(formData: FormData) {
    const { data } = await this.client.post("/recitations/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  }

  async getRecitation(id: string) {
    const { data } = await this.client.get(`/recitations/${id}`);
    return data;
  }

  async listRecitations(params?: Record<string, string | number>) {
    const { data } = await this.client.get("/recitations/", { params });
    return data;
  }

  async reviewRecitation(id: string, review: Record<string, unknown>) {
    const { data } = await this.client.post(`/recitations/${id}/review`, review);
    return data;
  }

  // ── Students ──────────────────────────────────────────────────────
  async getStudentProfile(studentId?: string) {
    const path = studentId ? `/students/${studentId}/profile` : "/students/me/profile";
    const { data } = await this.client.get(path);
    return data;
  }

  async getStudentSchedule() {
    const { data } = await this.client.get("/students/me/schedule");
    return data;
  }

  async listStudents(params?: Record<string, string | number>) {
    const { data } = await this.client.get("/students/", { params });
    return data;
  }

  // ── Analytics ─────────────────────────────────────────────────────
  async getMasjidAnalytics() {
    const { data } = await this.client.get("/analytics/masjid");
    return data;
  }

  async getTeacherSummary() {
    const { data } = await this.client.get("/analytics/teacher/summary");
    return data;
  }

  // ── Billing ───────────────────────────────────────────────────────
  async getSubscriptionTiers(country: string = "US") {
    const { data } = await this.client.get(`/billing/tiers?country=${country}`);
    return data;
  }

  async getUsage() {
    const { data } = await this.client.get("/billing/usage");
    return data;
  }

  // ── Tenants ───────────────────────────────────────────────────────
  async getMyTenant() {
    const { data } = await this.client.get("/tenants/me");
    return data;
  }
}

export const api = new ApiClient();
