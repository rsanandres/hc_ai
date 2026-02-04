/**
 * Axios instance configured for authentication with automatic token refresh
 */
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const axiosInstance = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true, // Required for sending/receiving cookies (refresh token)
});

// Request interceptor: Add access token to all requests
axiosInstance.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor: Handle 401 errors and automatic token refresh
axiosInstance.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        // If 401 Unauthorized and haven't retried yet
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;

            try {
                console.log('[Auth] Access token expired, attempting refresh...');

                // Call refresh endpoint (HttpOnly refresh token cookie sent automatically)
                const { data } = await axios.post(
                    `${API_BASE_URL}/auth/refresh`,
                    {},
                    { withCredentials: true }
                );

                // Update access token in localStorage
                localStorage.setItem('access_token', data.access_token);
                console.log('[Auth] Token refreshed successfully');

                // Retry original request with new token
                originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
                return axiosInstance(originalRequest);
            } catch (refreshError) {
                // Refresh failed - clear auth and redirect to login
                console.error('[Auth] Token refresh failed:', refreshError);
                localStorage.removeItem('access_token');
                window.location.href = '/login';
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
);

export default axiosInstance;
