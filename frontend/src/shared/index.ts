// Shared/cross-cutting utilities - public API
export { ThemeToggle } from '@/shared/components/ThemeToggle';
export { useTheme } from '@/shared/hooks/useTheme';
export type { Theme } from '@/shared/hooks/useTheme';
export { cn } from '@/shared/lib/utils';
export { apiUrl, ApiError, fetchApi } from '@/shared/api/httpClient';
export { checkHealth, ingestEvents } from '@/shared/api/systemApi';
export * from '@/shared/types/system';
