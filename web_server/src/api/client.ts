import axios from "axios";

const TOKEN_KEY = "ervongola_panel_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

// Impostata da AuthContext: permette al client di "sloggare" l'utente
// quando una richiesta torna 401, senza che ogni chiamante debba gestirlo.
let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

export const apiClient = axios.create({
  // In sviluppo resta vuoto: il proxy di Vite (vedi vite.config.ts) inoltra
  // /api verso il backend Flask su localhost:5000. In produzione, se
  // frontend e backend sono serviti da origini diverse, valorizzare
  // VITE_API_URL con l'URL pubblico del backend.
  baseURL: import.meta.env.VITE_API_URL || "",
});

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      onUnauthorized();
    }
    return Promise.reject(error);
  }
);

export function apiErrorMessage(error: unknown, fallback = "Si è verificato un errore."): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.error || error.message || fallback;
  }
  return fallback;
}

/** URL assoluto per l'EventSource dei log (che non passa da axios). */
export function logsStreamUrl(): string {
  const base = import.meta.env.VITE_API_URL || window.location.origin;
  const url = new URL("/api/logs/stream", base);
  url.searchParams.set("token", getToken() || "");
  return url.toString();
}
