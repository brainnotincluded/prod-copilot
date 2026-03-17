import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

export type UserRole = 'viewer' | 'editor' | 'admin'

export interface User {
  id: number
  email: string
  name: string | null
  role: UserRole
}

export interface AuthTokens {
  access_token: string
  token_type: string
  expires_in: number
}

const STORAGE_KEY = 'auth_user'
const TOKEN_KEY = 'auth_token'

const user = ref<User | null>(null)
const token = ref<string | null>(null)
const isLoading = ref(false)
const error = ref<string | null>(null)

// API base URL
const API_BASE_URL = ''  // Use relative URLs — Vite proxy handles /api/* routing

// Load from localStorage on init
const savedUser = localStorage.getItem(STORAGE_KEY)
const savedToken = localStorage.getItem(TOKEN_KEY)
if (savedUser && savedToken) {
  try {
    user.value = JSON.parse(savedUser)
    token.value = savedToken
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(TOKEN_KEY)
  }
}

// Helper function for API calls
async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers as Record<string, string>,
  }
  
  if (token.value) {
    headers['Authorization'] = `Bearer ${token.value}`
  }
  
  let response: Response
  try {
    response = await fetch(url, {
      ...options,
      headers,
    })
  } catch (networkErr: any) {
    throw new Error('Server unavailable. Please try again later.')
  }

  if (!response.ok) {
    let detail = ''
    try {
      const errorData = await response.json()
      detail = errorData.detail || errorData.message || ''
    } catch {
      // response body is not JSON
    }

    if (!detail) {
      if (response.status === 401) detail = 'Invalid email or password'
      else if (response.status === 403) detail = 'Access denied'
      else if (response.status === 422) detail = 'Invalid input data'
      else if (response.status >= 500) detail = 'Server error. Please try again later.'
      else detail = `Request failed (${response.status})`
    }

    throw new Error(detail)
  }

  return response.json()
}

export function useAuth() {
  const router = useRouter()

  const isAuthenticated = computed(() => !!user.value && !!token.value)
  const currentUser = computed(() => user.value)
  const currentToken = computed(() => token.value)
  
  const isViewer = computed(() => user.value?.role === 'viewer')
  const isEditor = computed(() => user.value?.role === 'editor')
  const isAdmin = computed(() => user.value?.role === 'admin')

  const canUpload = computed(() => 
    user.value ? ['editor', 'admin'].includes(user.value.role) : false
  )
  const canDelete = computed(() => user.value?.role === 'admin')
  const canApprove = computed(() => user.value?.role === 'admin')

  /**
   * Login user with email and password
   */
  const login = async (email: string, password: string): Promise<boolean> => {
    isLoading.value = true
    error.value = null

    try {
      const data = await apiCall<AuthTokens & { user: User }>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })

      user.value = data.user
      token.value = data.access_token
      
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data.user))
      localStorage.setItem(TOKEN_KEY, data.access_token)
      
      return true
    } catch (err: any) {
      error.value = err.message || 'Login failed. Please try again.'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Register a new user
   */
  const register = async (
    email: string,
    password: string,
    name: string
  ): Promise<boolean> => {
    isLoading.value = true
    error.value = null

    try {
      const data = await apiCall<AuthTokens & { user: User }>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password, name }),
      })

      user.value = data.user
      token.value = data.access_token
      
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data.user))
      localStorage.setItem(TOKEN_KEY, data.access_token)
      
      return true
    } catch (err: any) {
      error.value = err.message || 'Registration failed. Please try again.'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Fetch current user info
   */
  const fetchCurrentUser = async (): Promise<boolean> => {
    if (!token.value) return false
    
    try {
      const data = await apiCall<User>('/api/v1/auth/me')
      user.value = data
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
      return true
    } catch (err) {
      // Token might be invalid, clear it
      logout()
      return false
    }
  }

  /**
   * Logout user and clear session
   */
  const logout = async () => {
    try {
      if (token.value) {
        await apiCall('/api/v1/auth/logout', { method: 'POST' })
      }
    } catch {
      // Ignore errors on logout
    } finally {
      user.value = null
      token.value = null
      localStorage.removeItem(STORAGE_KEY)
      localStorage.removeItem(TOKEN_KEY)
      router.push('/login')
    }
  }

  /**
   * Change password
   */
  const changePassword = async (
    currentPassword: string,
    newPassword: string
  ): Promise<boolean> => {
    isLoading.value = true
    error.value = null

    try {
      await apiCall('/api/v1/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })
      return true
    } catch (err: any) {
      error.value = err.message || 'Failed to change password'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Get auth headers for API requests
   */
  const getAuthHeaders = (): Record<string, string> => {
    const headers: Record<string, string> = {}
    
    if (token.value) {
      headers['Authorization'] = `Bearer ${token.value}`
    }
    
    // Also send role header for backward compatibility
    if (user.value) {
      headers['X-User-Role'] = user.value.role
    }
    
    return headers
  }

  /**
   * Check if user has required role
   */
  const hasRole = (requiredRole: UserRole): boolean => {
    if (!user.value) return false
    
    const roleHierarchy: Record<UserRole, number> = {
      viewer: 0,
      editor: 1,
      admin: 2,
    }
    
    return roleHierarchy[user.value.role] >= roleHierarchy[requiredRole]
  }

  /**
   * Get user initials for avatar
   */
  const userInitials = computed(() => {
    if (!user.value?.name) return '?'
    return user.value.name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  })

  /**
   * Get avatar background color based on user id
   */
  const avatarColor = computed(() => {
    if (!user.value) return '#6366f1'
    const colors = [
      '#ef4444', '#f97316', '#f59e0b', '#84cc16',
      '#10b981', '#06b6d4', '#3b82f6', '#6366f1',
      '#8b5cf6', '#d946ef', '#f43f5e',
    ]
    return colors[(user.value.id || 0) % colors.length]
  })

  return {
    // State
    user: currentUser,
    token: currentToken,
    isLoading,
    error,
    
    // Computed
    isAuthenticated,
    role: computed(() => user.value?.role ?? null),
    isViewer,
    isEditor,
    isAdmin,
    canUpload,
    canDelete,
    canApprove,
    userInitials,
    avatarColor,
    
    // Methods
    login,
    register,
    logout,
    fetchCurrentUser,
    changePassword,
    getAuthHeaders,
    hasRole,
  }
}
