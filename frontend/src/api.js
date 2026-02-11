import axios from 'axios';

// Use REACT_APP_BACKEND_URL if set, otherwise use same-origin (empty string)
// This allows the frontend to work both as a separate deployment and when served by the backend
const API_URL = process.env.REACT_APP_BACKEND_URL || '';
const API_KEY = process.env.REACT_APP_API_KEY;

const api = axios.create({
  baseURL: API_URL,
  timeout: 300000,
});

// Add request interceptor for API key
api.interceptors.request.use((config) => {
  if (API_KEY) {
    config.headers['X-API-Key'] = API_KEY;
  }
  return config;
});

// Add response interceptor for better error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Provide user-friendly error messages
    if (error.code === 'ECONNABORTED') {
      error.userMessage = 'Request timeout. Please try again.';
    } else if (error.message === 'Network Error' || !error.response) {
      error.userMessage = 'Cannot connect to server. Please check your connection.';
    } else if (error.response?.status === 503) {
      error.userMessage = 'Service temporarily unavailable. Please try again later.';
    } else if (error.response?.status === 429) {
      error.userMessage = 'Rate limit exceeded. Please wait a moment and try again.';
    } else if (error.response?.status >= 500) {
      // For 500 errors, try to get the detail from the response
      error.userMessage = error.response?.data?.detail || 'Server error. Please try again later.';
    } else if (error.response?.data?.detail) {
      error.userMessage = error.response.data.detail;
    } else {
      error.userMessage = error.message || 'An error occurred';
    }
    return Promise.reject(error);
  }
);

export const getHealth = () => api.get('/api/health');
export const getDashboardStats = () => api.get('/api/dashboard/stats');
export const getCompanies = () => api.get('/api/companies');
export const getCompany = (id) => api.get(`/api/companies/${id}`);
export const deleteCompany = (id) => api.delete(`/api/companies/${id}`);
export const uploadDeck = (file, companyWebsite) => {
  const formData = new FormData();
  formData.append('file', file);
  if (companyWebsite) {
    formData.append('company_website', companyWebsite);
  }
  return api.post('/api/decks/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const getDeckStatus = (deckId) => api.get(`/api/decks/${deckId}/status`);
export const getCompanyScore = (companyId) => api.get(`/api/companies/${companyId}/score`);
export const getCompanyMemo = (companyId) => api.get(`/api/companies/${companyId}/memo`);
export const triggerEnrichment = (companyId) => api.post(`/api/companies/${companyId}/enrich`);
export const getWebsiteIntelligence = (companyId) => api.get(`/api/companies/${companyId}/website-intelligence`);
export const rerunWebsiteIntelligence = (companyId) => api.post(`/api/companies/${companyId}/website-intelligence/rerun`);

export default api;
