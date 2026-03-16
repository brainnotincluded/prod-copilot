/**
 * Mock data for API Maps testing
 * This provides sample endpoints for visual regression testing
 */

export interface MockEndpoint {
  id: number
  swagger_source_id: number
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  path: string
  summary: string
  description?: string
  parameters: Array<{
    name: string
    in: 'query' | 'path' | 'body' | 'header'
    required?: boolean
    type?: string
    schema?: Record<string, any>
  }>
  request_body?: Record<string, any>
  response_schema?: Record<string, any>
}

export interface MockSwaggerSource {
  id: number
  name: string
  url?: string
  base_url?: string
  endpoint_count: number
  created_at: string
}

export const mockSwaggerSources: MockSwaggerSource[] = [
  {
    id: 1,
    name: 'JSONPlaceholder API',
    url: 'https://jsonplaceholder.typicode.com',
    base_url: 'https://jsonplaceholder.typicode.com',
    endpoint_count: 6,
    created_at: '2026-03-15T10:00:00Z',
  },
  {
    id: 2,
    name: 'Pet Store API',
    url: 'https://petstore.swagger.io/v2/swagger.json',
    base_url: 'https://petstore.swagger.io/v2',
    endpoint_count: 8,
    created_at: '2026-03-14T15:30:00Z',
  },
]

export const mockEndpoints: MockEndpoint[] = [
  // JSONPlaceholder - Posts
  {
    id: 1,
    swagger_source_id: 1,
    method: 'GET',
    path: '/posts',
    summary: 'Get all posts',
    description: 'Retrieve a list of all posts',
    parameters: [
      { name: 'userId', in: 'query', required: false, type: 'integer' },
      { name: '_limit', in: 'query', required: false, type: 'integer' },
    ],
    response_schema: {
      type: 'array',
      items: { $ref: '#/components/schemas/Post' },
    },
  },
  {
    id: 2,
    swagger_source_id: 1,
    method: 'GET',
    path: '/posts/{id}',
    summary: 'Get post by ID',
    description: 'Retrieve a specific post by its ID',
    parameters: [
      { name: 'id', in: 'path', required: true, type: 'integer' },
    ],
    response_schema: { $ref: '#/components/schemas/Post' },
  },
  {
    id: 3,
    swagger_source_id: 1,
    method: 'POST',
    path: '/posts',
    summary: 'Create a new post',
    description: 'Create a new post with the provided data',
    parameters: [],
    request_body: {
      required: true,
      content: {
        'application/json': {
          schema: { $ref: '#/components/schemas/PostInput' },
        },
      },
    },
    response_schema: { $ref: '#/components/schemas/Post' },
  },
  {
    id: 4,
    swagger_source_id: 1,
    method: 'PUT',
    path: '/posts/{id}',
    summary: 'Update a post',
    description: 'Update an existing post by ID',
    parameters: [
      { name: 'id', in: 'path', required: true, type: 'integer' },
    ],
    request_body: {
      required: true,
      content: {
        'application/json': {
          schema: { $ref: '#/components/schemas/PostInput' },
        },
      },
    },
    response_schema: { $ref: '#/components/schemas/Post' },
  },
  {
    id: 5,
    swagger_source_id: 1,
    method: 'DELETE',
    path: '/posts/{id}',
    summary: 'Delete a post',
    description: 'Delete a post by its ID',
    parameters: [
      { name: 'id', in: 'path', required: true, type: 'integer' },
    ],
    response_schema: { type: 'object' },
  },
  // JSONPlaceholder - Users
  {
    id: 6,
    swagger_source_id: 1,
    method: 'GET',
    path: '/users',
    summary: 'Get all users',
    description: 'Retrieve a list of all users',
    parameters: [
      { name: 'username', in: 'query', required: false, type: 'string' },
    ],
    response_schema: {
      type: 'array',
      items: { $ref: '#/components/schemas/User' },
    },
  },
  {
    id: 7,
    swagger_source_id: 1,
    method: 'GET',
    path: '/users/{id}',
    summary: 'Get user by ID',
    description: 'Retrieve a specific user by ID',
    parameters: [
      { name: 'id', in: 'path', required: true, type: 'integer' },
    ],
    response_schema: { $ref: '#/components/schemas/User' },
  },
  // Posts/{id}/Comments - nested resource
  {
    id: 8,
    swagger_source_id: 1,
    method: 'GET',
    path: '/posts/{id}/comments',
    summary: 'Get post comments',
    description: 'Retrieve comments for a specific post',
    parameters: [
      { name: 'id', in: 'path', required: true, type: 'integer' },
    ],
    response_schema: {
      type: 'array',
      items: { $ref: '#/components/schemas/Comment' },
    },
  },
  // Pet Store API endpoints
  {
    id: 9,
    swagger_source_id: 2,
    method: 'GET',
    path: '/pet/findByStatus',
    summary: 'Find pets by status',
    description: 'Find pets based on their status',
    parameters: [
      { name: 'status', in: 'query', required: true, type: 'array', schema: { items: { type: 'string', enum: ['available', 'pending', 'sold'] } } },
    ],
    response_schema: {
      type: 'array',
      items: { $ref: '#/components/schemas/Pet' },
    },
  },
  {
    id: 10,
    swagger_source_id: 2,
    method: 'GET',
    path: '/pet/{petId}',
    summary: 'Get pet by ID',
    description: 'Retrieve a pet by its ID',
    parameters: [
      { name: 'petId', in: 'path', required: true, type: 'integer', schema: { format: 'int64' } },
    ],
    response_schema: { $ref: '#/components/schemas/Pet' },
  },
  {
    id: 11,
    swagger_source_id: 2,
    method: 'POST',
    path: '/pet',
    summary: 'Add a new pet',
    description: 'Add a new pet to the store',
    parameters: [],
    request_body: {
      required: true,
      content: {
        'application/json': {
          schema: { $ref: '#/components/schemas/Pet' },
        },
      },
    },
    response_schema: { $ref: '#/components/schemas/Pet' },
  },
  {
    id: 12,
    swagger_source_id: 2,
    method: 'PUT',
    path: '/pet',
    summary: 'Update an existing pet',
    description: 'Update an existing pet',
    parameters: [],
    request_body: {
      required: true,
      content: {
        'application/json': {
          schema: { $ref: '#/components/schemas/Pet' },
        },
      },
    },
    response_schema: { $ref: '#/components/schemas/Pet' },
  },
  {
    id: 13,
    swagger_source_id: 2,
    method: 'DELETE',
    path: '/pet/{petId}',
    summary: 'Delete a pet',
    description: 'Delete a pet by ID',
    parameters: [
      { name: 'petId', in: 'path', required: true, type: 'integer', schema: { format: 'int64' } },
      { name: 'api_key', in: 'header', required: false, type: 'string' },
    ],
    response_schema: { type: 'object' },
  },
  {
    id: 14,
    swagger_source_id: 2,
    method: 'POST',
    path: '/pet/{petId}/uploadImage',
    summary: 'Upload pet image',
    description: 'Upload an image for a pet',
    parameters: [
      { name: 'petId', in: 'path', required: true, type: 'integer', schema: { format: 'int64' } },
      { name: 'additionalMetadata', in: 'query', required: false, type: 'string' },
    ],
    request_body: {
      content: {
        'multipart/form-data': {
          schema: {
            type: 'object',
            properties: {
              file: { type: 'string', format: 'binary' },
            },
          },
        },
      },
    },
    response_schema: { $ref: '#/components/schemas/ApiResponse' },
  },
]

// Mock API handlers for testing
export function mockApiMapsFetch(url: string): Promise<Response> {
  if (url.includes('/endpoints/list')) {
    return Promise.resolve(
      new Response(JSON.stringify(mockEndpoints), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )
  }
  
  if (url.includes('/swagger/list')) {
    return Promise.resolve(
      new Response(JSON.stringify(mockSwaggerSources), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )
  }
  
  if (url.includes('/endpoints/stats')) {
    return Promise.resolve(
      new Response(
        JSON.stringify({
          total: mockEndpoints.length,
          by_method: {
            GET: 7,
            POST: 4,
            PUT: 2,
            DELETE: 2,
            PATCH: 0,
          },
          by_source: {
            'JSONPlaceholder API': 8,
            'Pet Store API': 6,
          },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      )
    )
  }
  
  return Promise.reject(new Error(`Unhandled mock URL: ${url}`))
}
