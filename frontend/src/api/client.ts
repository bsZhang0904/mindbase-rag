import axios from 'axios'

const TOKEN_KEY = 'mindbase_token'

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface User {
  user_id: string
  email: string
  username: string
}

export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  document_count: number
  created_at: string
}

export interface DocumentItem {
  id: string
  title: string
  file_type: string
  file_size: number
  status: string
  chunk_count: number
  error_message: string | null
  created_at: string
}

export interface Conversation {
  id: string
  title: string | null
  kb_id: string
  created_at: string
  updated_at: string
}

export interface Citation {
  index: number
  chunk_id: string
  document_title: string
  page_number: number | null
  excerpt: string
  score: number | null
}

export interface Message {
  id: string
  role: string
  content: string
  citations: Citation[]
  created_at: string
}

export async function register(email: string, username: string, password: string) {
  const { data } = await api.post<ApiResponse<User>>('/auth/register', { email, username, password })
  return data.data!
}

export async function login(email: string, password: string) {
  const { data } = await api.post<ApiResponse<{ access_token: string }>>('/auth/login', { email, password })
  setToken(data.data!.access_token)
}

export async function getMe() {
  const { data } = await api.get<ApiResponse<User>>('/auth/me')
  return data.data!
}

export async function listKnowledgeBases() {
  const { data } = await api.get<ApiResponse<{ items: KnowledgeBase[]; total: number }>>('/knowledge-bases')
  return data.data!
}

export async function createKnowledgeBase(name: string, description?: string) {
  const { data } = await api.post<ApiResponse<KnowledgeBase>>('/knowledge-bases', { name, description })
  return data.data!
}

export async function deleteKnowledgeBase(id: string) {
  await api.delete(`/knowledge-bases/${id}`)
}

export async function listDocuments(kbId: string) {
  const { data } = await api.get<ApiResponse<DocumentItem[]>>(`/knowledge-bases/${kbId}/documents`)
  return data.data!
}

export async function uploadDocument(kbId: string, file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<ApiResponse<{ document_id: string; status: string }>>(
    `/knowledge-bases/${kbId}/documents`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return data.data!
}

export async function getDocument(docId: string) {
  const { data } = await api.get<ApiResponse<DocumentItem>>(`/documents/${docId}`)
  return data.data!
}

export async function deleteDocument(docId: string) {
  await api.delete(`/documents/${docId}`)
}

export async function listConversations(kbId: string) {
  const { data } = await api.get<ApiResponse<Conversation[]>>(`/knowledge-bases/${kbId}/conversations`)
  return data.data!
}

export async function createConversation(kbId: string, title?: string) {
  const { data } = await api.post<ApiResponse<Conversation>>(`/knowledge-bases/${kbId}/conversations`, { title })
  return data.data!
}

export async function getMessages(convId: string) {
  const { data } = await api.get<ApiResponse<{ items: Message[] }>>(`/conversations/${convId}/messages`)
  return data.data!.items
}

export async function chat(convId: string, question: string) {
  const { data } = await api.post<ApiResponse<{ message_id: string; answer: string; citations: Citation[]; latency_ms: number }>>(
    `/conversations/${convId}/chat`,
    { question }
  )
  return data.data!
}

export async function chatStream(
  convId: string,
  question: string,
  onToken: (token: string) => void
): Promise<{ message_id: string; citations: Citation[] }> {
  const token = getToken()
  const response = await fetch(`/api/v1/conversations/${convId}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
  })

  if (!response.ok) throw new Error('Stream request failed')

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result = { message_id: '', citations: [] as Citation[] }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''

    for (const event of events) {
      const lines = event.split('\n')
      let eventType = ''
      let eventData = ''
      for (const line of lines) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim()
        if (line.startsWith('data:')) eventData = line.slice(5).trim()
      }
      if (eventType === 'token' && eventData) {
        const parsed = JSON.parse(eventData)
        onToken(parsed.content)
      }
      if (eventType === 'done' && eventData) {
        result = JSON.parse(eventData)
      }
    }
  }
  return result
}
