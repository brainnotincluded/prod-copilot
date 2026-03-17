export type ResultType = 'text' | 'list' | 'table' | 'map' | 'chart' | 'image' | 'dashboard'

export interface QueryResult {
  type: ResultType
  data: Record<string, any>
  metadata?: Record<string, any>
}

export interface OrchestrationStep {
  step: number
  action: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'error'
  result?: Record<string, any>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  steps?: OrchestrationStep[]
  result?: QueryResult
  reasoning?: string
  timestamp: Date
}

export interface SwaggerSource {
  id: number
  name: string
  url?: string
  base_url?: string
  endpoint_count: number
  created_at: string
}

export interface SwaggerUploadResult {
  id: number
  name: string
  base_url?: string
  endpoints_count: number
  message: string
}

export interface WebSocketMessage {
  type: 'step' | 'result' | 'error' | 'done' | 'chat_token' | 'reasoning'
  data: any
}

export interface EndpointItem {
  id: number
  swagger_source_id: number
  method: string
  path: string
  summary?: string | null
  description?: string | null
  parameters?: Array<Record<string, any>> | null
  request_body?: Record<string, any> | null
  response_schema?: Record<string, any> | null
}

export interface EndpointStats {
  total: number
  by_method: Record<string, number>
  by_source: Record<string, number>
}
