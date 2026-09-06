import http from './http'
import { useAuthStore } from '../stores/auth'

// ===== 认证 =====
export const register = (d: { username: string; password: string; nickname?: string }) =>
  http.post('/auth/register', d)
export const login = (d: { username: string; password: string }) => http.post('/auth/login', d)
export const me = () => http.get('/auth/me')

// ===== 模型 =====
export interface ModelInfo { id: string; name: string; vendor: string; free: boolean; description: string }
export const listModels = () => http.get<never, ModelInfo[]>('/models')

// ===== 会话与消息 =====
export interface Conversation { id: number; title: string }
export const listSessions = () => http.get<never, Conversation[]>('/sessions')
export const createSession = () => http.post<never, Conversation>('/sessions')
export const listMessages = (sid: number) => http.get<never, MessageItem[]>(`/sessions/${sid}/messages`)
export interface MessageItem { id: number; role: string; content: string; citations?: { title: string; url: string }[] | null }

interface SSEHandlers {
  onDelta: (text: string) => void
  onProgress: (data: any) => void
  onError: (message: string) => void
}

async function postSSE(
  url: string,
  body: Record<string, unknown>,
  handlers: SSEHandlers,
  signal?: AbortSignal,
) {
  const auth = useAuthStore()
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
    body: JSON.stringify(body),
    signal,
  })
  if (!resp.ok || !resp.body) throw new Error(`请求失败（HTTP ${resp.status}）`)

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const raw = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      const event = raw.match(/^event: (.+)$/m)?.[1]
      const data = raw.match(/^data: (.+)$/m)?.[1]
      if (!event || !data) continue
      const payload = JSON.parse(data)
      if (event === 'message_delta') handlers.onDelta(payload.content)
      else if (event === 'task_progress') handlers.onProgress(payload)
      else if (event === 'error') handlers.onError(payload.message)
    }
  }
}

/**
 * SSE 流式问答（Spec 00 §5.3：event = message_delta | task_progress | error）
 * POST + fetch ReadableStream（EventSource 不支持 POST/自定义头）
 */
export async function chatStream(
  sid: number,
  body: { content: string; model_id: string },
  handlers: { onDelta: (t: string) => void; onProgress: (d: any) => void; onError: (m: string) => void },
  signal?: AbortSignal,
) {
  return postSSE(`/api/v1/sessions/${sid}/chat/stream`, body, handlers, signal)
}

// ===== 文章 =====
export interface Article { id: number; author_id: number; title: string; status: string; source: string; content_md: string }
export const generateArticleStream = (
  body: { topic: string; model_id: string },
  handlers: SSEHandlers,
  signal?: AbortSignal,
) => postSSE('/api/v1/articles/generate', body, handlers, signal)
export const myArticles = () => http.get<never, Article[]>('/articles/mine')
export const publishArticle = (id: number) => http.post<never, Article>(`/articles/${id}/publish`)
