import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import type {
  Item,
  ItemCreate,
  ItemUpdate,
  Container,
  ContainerCreate,
  ContainerUpdate,
  PackingListUpload,
  RunCreate,
  RunCreateQuick,
  RunResult,
  RunSummary,
  ValidationResponse,
  PackingList,
  PackingListSummary,
  PackingListCreate,
  PackingListUpdate,
} from '../types/api'

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 600000, // 10 minutes
})

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('auth_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => Promise.reject(error)
)

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown,
    public errors?: Array<{ field: string; message: string }>
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const { status, data } = error.response
      let message = error.message || 'Request failed'
      if (typeof (data as any)?.detail === 'string') {
        message = (data as any).detail
      } else if (Array.isArray((data as any)?.detail)) {
        message = (data as any).detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ')
      } else if (typeof (data as any)?.message === 'string') {
        message = (data as any).message
      } else if ((data as any)?.detail && typeof (data as any).detail === 'object') {
        message = JSON.stringify((data as any).detail)
      }
      const errors = (data as any)?.errors
      throw new ApiError(message, status, data, errors)
    } else if (error.code === 'ECONNABORTED' || error.message?.toLowerCase().includes('timeout')) {
      throw new ApiError('Request timed out while calculating loading plan. You can reduce generations/population size or increase timeout.', 408)
    } else if (error.request) {
      throw new ApiError('Network error - unable to reach server. Please check backend status.', 0)
    } else {
      throw new ApiError(error.message, 0)
    }
  }
)

export { api, ApiError }

export const itemApi = {
  list: (skip = 0, limit = 100) =>
    api.get<Item[]>(`/items`, { params: { skip, limit } }).then((r) => r.data),
  get: (id: number) =>
    api.get<Item>(`/items/${id}`).then((r) => r.data),
  create: (item: ItemCreate) =>
    api.post<Item>('/items', item).then((r) => r.data),
  update: (id: number, item: ItemUpdate) =>
    api.put<Item>(`/items/${id}`, item).then((r) => r.data),
  delete: (id: number) =>
    api.delete(`/items/${id}`).then((r) => r.data),
  uploadCsv: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ success: boolean; created: number; updated: number; errors: string[]; total_rows: number }>('/items/upload-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
}

export const containerApi = {
  list: (skip = 0, limit = 100) =>
    api.get<Container[]>(`/containers`, { params: { skip, limit } }).then((r) => r.data),
  get: (id: number) =>
    api.get<Container>(`/containers/${id}`).then((r) => r.data),
  create: (container: ContainerCreate) =>
    api.post<Container>('/containers', container).then((r) => r.data),
  update: (id: number, container: ContainerUpdate) =>
    api.put<Container>(`/containers/${id}`, container).then((r) => r.data),
  delete: (id: number) =>
    api.delete(`/containers/${id}`).then((r) => r.data),
  uploadCsv: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ success: boolean; created: number; updated: number; errors: string[]; total_rows: number }>('/containers/upload-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
}

export const packingListApi = {
  validate: (upload: PackingListUpload) =>
    api.post<ValidationResponse>('/packing-lists/validate', upload).then((r) => r.data),
  validateCsv: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<ValidationResponse>('/packing-lists/validate-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
  uploadCsv: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ success: boolean; rows_parsed: number; errors: string[]; preview: any }>('/packing-lists/upload-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
  list: (skip = 0, limit = 100) =>
    api.get<PackingListSummary[]>(`/packing-lists`, { params: { skip, limit } }).then((r) => r.data),
  get: (id: number) =>
    api.get<PackingList>(`/packing-lists/${id}`).then((r) => r.data),
  create: (packingList: PackingListCreate) =>
    api.post<PackingList>('/packing-lists', packingList).then((r) => r.data),
  update: (id: number, packingList: PackingListUpdate) =>
    api.put<PackingList>(`/packing-lists/${id}`, packingList).then((r) => r.data),
  delete: (id: number) =>
    api.delete(`/packing-lists/${id}`).then((r) => r.data),
  uploadAndSaveCsv: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ success: boolean; packing_list_id: number; name: string; rows_parsed: number; errors: string[]; preview: any }>('/packing-lists/upload-csv-and-save', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
}

export const runApi = {
  list: (skip = 0, limit = 100) =>
    api.get<RunSummary[]>(`/runs`, { params: { skip, limit } }).then((r) => r.data),
  get: (runId: string) =>
    api.get<RunResult>(`/runs/${runId}`).then((r) => r.data),
  create: (run: RunCreate) =>
    api.post<RunResult>('/runs', run).then((r) => r.data),
  createQuick: (run: RunCreateQuick) =>
    api.post<RunResult>('/runs/quick', run).then((r) => r.data),
  delete: (runId: string) =>
    api.delete(`/runs/${runId}`).then((r) => r.data),
}

export const uploadApi = {
  upload: (type: 'items' | 'containers' | 'packing-lists', file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ success: boolean; created?: number; updated?: number; errors: string[]; total_rows?: number; rows_parsed?: number; preview?: any; packing_list_id?: number; name?: string }>(`/upload/${type}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
}

export default api