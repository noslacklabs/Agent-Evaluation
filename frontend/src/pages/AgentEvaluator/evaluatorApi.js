import axios from 'axios';

const evaluatorApi = axios.create({
  baseURL: import.meta.env.VITE_EVALUATOR_API_URL || 'http://localhost:8002/api',
  timeout: 130000,
});

export const errorMessage = (error, fallback = 'Something went wrong') => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(', ');
  return error?.message || fallback;
};

export default evaluatorApi;
