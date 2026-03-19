import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || '/api/v1';

// 统一日期格式化函数 - 转换为 UTC+8 (北京时间)
export const formatDateTime = (dateString) => {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
};

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message;
    return Promise.reject(new Error(message));
  }
);

// Dataset APIs
export const datasetApi = {
  list: (params) => api.get('/datasets', { params }),
  get: (id) => api.get(`/datasets/${id}`),
  create: (data) => api.post('/datasets', data),
  update: (id, data) => api.put(`/datasets/${id}`, data),
  delete: (id) => api.delete(`/datasets/${id}`),
  import: (id, data) => api.post(`/datasets/${id}/import`, data),
  export: (id, format) => api.get(`/datasets/${id}/export?format=${format}`),
  listCases: (id, params) => api.get(`/datasets/${id}/cases`, { params }),
  addCase: (id, data) => api.post(`/datasets/${id}/cases`, data),
  updateCase: (datasetId, caseId, data) => api.put(`/datasets/${datasetId}/cases/${caseId}`, data),
  deleteCase: (datasetId, caseId) => api.delete(`/datasets/${datasetId}/cases/${caseId}`),
};

// Scoring Rule APIs
export const ruleApi = {
  list: (params) => api.get('/rules', { params }),
  get: (id) => api.get(`/rules/${id}`),
  create: (data) => api.post('/rules', data),
  update: (id, data) => api.put(`/rules/${id}`, data),
  delete: (id) => api.delete(`/rules/${id}`),
};

// Evaluation APIs
export const evalApi = {
  listTasks: (params) => api.get('/evaluate/tasks', { params }),
  getTask: (id) => api.get(`/evaluate/tasks/${id}`),
  createTask: (data) => api.post('/evaluate/tasks', data),
  cancelTask: (id) => api.post(`/evaluate/tasks/${id}/cancel`),
  getTaskResults: (id, params) => api.get(`/evaluate/tasks/${id}/results`, { params }),
  getTaskStatus: (id) => api.get(`/evaluate/tasks/${id}/status`),
  quickEval: (data) => api.post('/evaluate/quick', data),
};

// Report APIs
export const reportApi = {
  list: (params) => api.get('/reports', { params }),
  get: (id) => api.get(`/reports/${id}`),
  download: (id, format) => api.get(`/reports/${id}/download?format=${format}`),
  getDashboardStats: () => api.get('/reports/dashboard/stats'),
};

// Quality Gate APIs
export const gateApi = {
  list: (params) => api.get('/gates', { params }),
  get: (id) => api.get(`/gates/${id}`),
  create: (data) => api.post('/gates', data),
  update: (id, data) => api.put(`/gates/${id}`, data),
  delete: (id) => api.delete(`/gates/${id}`),
  check: (id, data) => api.post(`/gates/${id}/check`, data),
};

export default api;
