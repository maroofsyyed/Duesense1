import axios from 'axios';

// Use REACT_APP_BACKEND_URL if set, otherwise use same-origin (empty string)
// This allows the frontend to work both as a separate deployment and when served by the backend
const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const api = axios.create({
  baseURL: API_URL,
  timeout: 300000,
});

// Add response interceptor for better error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle network errors
    if (error.code === 'ECONNABORTED') {
      error.message = 'Request timeout. The backend may be slow or unavailable.';
    } else if (error.message === 'Network Error' || !error.response) {
      error.message = 'Cannot connect to backend. Please check your connection.';
    } else if (error.response?.status === 503) {
      error.message = 'Backend service is unavailable. Please try again later.';
    } else if (error.response?.status >= 500) {
      error.message = 'Backend server error. Please try again later.';
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
