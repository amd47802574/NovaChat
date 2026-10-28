import axios from 'axios';

const api = axios.create({
  timeout: 60000,
});

// 请求拦截器：自动附加登录令牌
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器：统一处理登录过期
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    const requestUrl: string = error.config?.url || '';
    // /auth/* 接口的 401 属于业务失败（如账号密码错误），
    // 由表单内联提示处理，不触发全局“登录过期”逻辑。
    const isAuthRequest = requestUrl.startsWith('/auth/');
    if (
      error.response &&
      error.response.status === 401 &&
      !isAuthRequest
    ) {
      localStorage.removeItem('accessToken');
      // 通知应用清理登录状态
      window.dispatchEvent(new CustomEvent('unauthorized'));
    }
    return Promise.reject(error);
  }
);

export default api;
