import axios from "axios";
import type {
  Task,
  TaskConfig,
  StepLog,
  Execution,
  LLMProvider,
  ReviewItem,
  AuditItem,
  TemplateItem,
} from "@/types";

const api = axios.create({
  // 开发模式走 Vite 代理；打包（Tauri/静态托管）后直接访问本地后端
  baseURL: import.meta.env.DEV ? "/api" : "http://127.0.0.1:8710/api",
  timeout: 60000,
});

// === 任务 ===
export const getTasks = () => api.get<Task[]>("/tasks").then((r) => r.data);
export const getTask = (id: string) => api.get<Task>(`/tasks/${id}`).then((r) => r.data);
export const createTask = (name: string, config: TaskConfig) =>
  api.post("/tasks", { name, config }).then((r) => r.data);
export const updateTask = (id: string, data: Partial<Task>) =>
  api.put(`/tasks/${id}`, data).then((r) => r.data);
export const deleteTask = (id: string) => api.delete(`/tasks/${id}`).then((r) => r.data);
export const runTask = (id: string) => api.post(`/tasks/${id}/run`).then((r) => r.data);
export const stopTask = (id: string) => api.post(`/tasks/${id}/stop`).then((r) => r.data);
export const getHistory = (id: string) =>
  api.get<Execution[]>(`/tasks/${id}/history`).then((r) => r.data);

// === 自然语言 ===
export const parseNL = (text: string) =>
  api.post<{ config: TaskConfig }>("/nl/parse", { text }).then((r) => r.data);
// 多轮修改：携带已有方案 + 用户新要求，AI 返回修改后的方案
export const refineNL = (text: string, config: TaskConfig) =>
  api.post<{ config: TaskConfig }>("/nl/refine", { text, config }).then((r) => r.data);

// === 报告 ===
export const getLatestReport = (taskId: string) =>
  api.get<{ run_id: string; report_path: string }>(`/reports/${taskId}`).then((r) => r.data);
export const getReportDetail = (taskId: string, runId: string) =>
  api
    .get<{ execution: Execution; steps: StepLog[] }>(`/reports/${taskId}/${runId}`)
    .then((r) => r.data);

// === 录制 ===
export const startRecording = (start_url: string) =>
  api.post<{ session_id: string }>("/recording/start", { start_url }).then((r) => r.data);
export const stopRecording = () =>
  api.post<{ steps: TaskConfig["steps"] }>("/recording/stop").then((r) => r.data);
export const getRecordingStatus = () =>
  api.get<{ recording: boolean; session_id?: string; event_count?: number }>(
    "/recording/status"
  ).then((r) => r.data);
export const forceStopRecording = () =>
  api.post<{ ok: boolean }>("/recording/force-stop").then((r) => r.data);

// === 设置 ===
export const getSettings = () => api.get<Record<string, string>>("/settings").then((r) => r.data);
export const getProviders = () =>
  api.get<{ providers: LLMProvider[] }>("/settings/providers").then((r) => r.data);
export const updateSettings = (data: Record<string, any>) =>
  api.put("/settings", data).then((r) => r.data);
export const testLLM = () => api.post("/settings/test-llm").then((r) => r.data);

// === 浏览器接管 ===
export const launchBrowser = () =>
  api.post<{ ok: boolean; cdp_url?: string; msg?: string }>("/browser/launch").then((r) => r.data);

// === 人工审核队列 ===
export const getReviews = (params: {
  status?: string;
  task_id?: string;
  page?: number;
  page_size?: number;
}) => api.get<{ items: ReviewItem[]; total: number }>("/reviews", { params }).then((r) => r.data);
export const getPendingReviewCount = () =>
  api.get<{ count: number }>("/reviews/pending-count").then((r) => r.data);
export const getReview = (id: string) =>
  api.get<ReviewItem>(`/reviews/${id}`).then((r) => r.data);
export const approveReview = (id: string, data: { operator?: string; note?: string }) =>
  api.post(`/reviews/${id}/approve`, data).then((r) => r.data);
export const rejectReview = (id: string, data: { operator?: string; note?: string }) =>
  api.post(`/reviews/${id}/reject`, data).then((r) => r.data);
export const updateReview = (
  id: string,
  data: { operator?: string; note?: string; corrected_data?: any }
) => api.post(`/reviews/${id}/update`, data).then((r) => r.data);

// === 操作审计日志 ===
export const getAuditLogs = (params: {
  operator?: string;
  action?: string;
  target_type?: string;
  start?: string;
  end?: string;
  page?: number;
  page_size?: number;
}) => api.get<{ items: AuditItem[]; total: number }>("/audit", { params }).then((r) => r.data);
export const exportAuditLogs = (params: {
  operator?: string;
  action?: string;
  target_type?: string;
  start?: string;
  end?: string;
}) => {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v) qs.append(k, String(v));
  });
  return `/audit/export?${qs.toString()}`;
};

// === 模板中心 ===
export const getTemplates = () =>
  api.get<TemplateItem[]>("/templates").then((r) => r.data);
export const uploadTemplate = (formData: FormData) =>
  api.post<{ id: string; name: string }>("/templates/upload", formData).then((r) => r.data);
export const deleteTemplate = (id: string) =>
  api.delete(`/templates/${id}`).then((r) => r.data);
export const downloadTemplateUrl = (id: string) => `/templates/${id}/download`;

export default api;