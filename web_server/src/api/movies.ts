import { apiClient } from "./client";

export type MovieStatus = "visto" | "da_guardare";

export interface Movie {
  id: number;
  title: string;
  link: string;
  platform: string;
  status: MovieStatus;
  cover_url: string;
  genre: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface MovieInput {
  title: string;
  link?: string;
  platform?: string;
  status?: MovieStatus;
  cover_url?: string;
  genre?: string;
  notes?: string;
}

export interface MovieFilters {
  status?: MovieStatus | "";
  platform?: string;
  genre?: string;
  search?: string;
}

export interface MoviePage {
  items: Movie[];
  total: number;
  page: number;
  page_size: number;
}

export async function listMovies(
  filters: MovieFilters = {},
  page = 1,
  pageSize = 12
): Promise<MoviePage> {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (filters.status) params.status = filters.status;
  if (filters.platform) params.platform = filters.platform;
  if (filters.genre) params.genre = filters.genre;
  if (filters.search) params.search = filters.search;

  const res = await apiClient.get<MoviePage>("/api/movies", { params });
  return res.data;
}

export async function getMovie(id: number): Promise<Movie> {
  const res = await apiClient.get<Movie>(`/api/movies/${id}`);
  return res.data;
}

export async function createMovie(data: MovieInput): Promise<Movie> {
  const res = await apiClient.post<Movie>("/api/movies", data);
  return res.data;
}

export async function updateMovie(id: number, data: Partial<MovieInput>): Promise<Movie> {
  const res = await apiClient.put<Movie>(`/api/movies/${id}`, data);
  return res.data;
}

export async function deleteMovie(id: number): Promise<void> {
  await apiClient.delete(`/api/movies/${id}`);
}
