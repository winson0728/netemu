const API = {
  async request(method, path, body) {
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },
  interfaces: {
    list: () => API.request('GET', '/api/interfaces/'),
  },
  rules: {
    list: () => API.request('GET', '/api/rules/'),
    save: (body) => API.request('POST', '/api/rules/', body),
    clear: (id) => API.request('POST', `/api/rules/${id}/clear`),
    delete: (id) => API.request('DELETE', `/api/rules/${id}`),
    disconnect: (iface, disconnect) => API.request('POST', '/api/rules/disconnect', { interface: iface, disconnect }),
    setMode: (mode, lines) => API.request('POST', '/api/rules/mode', { mode, lines }),
  },
  profiles: {
    list: () => API.request('GET', '/api/profiles/'),
    save: (body) => API.request('POST', '/api/profiles/', body),
    delete: (id) => API.request('DELETE', `/api/profiles/${id}`),
  },
  schedule: {
    disconnect: (iface, duration_s) => API.request('POST', '/api/schedule/disconnect', { interface: iface, duration_s }),
  },
};
