// Shared HTTP client for backend communication

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/** Absolute URL — EventSource can't go through `fetchApi`. Same base as fetch so Docker's VITE_API_URL doesn't break streams. */
export function apiUrl(endpoint: string): string {
  return `${API_BASE_URL}${endpoint}`;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      `API error: ${response.statusText}`,
      errorData
    );
  }

  return response.json();
}
