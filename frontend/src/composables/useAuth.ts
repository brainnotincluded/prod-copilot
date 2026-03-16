import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

export type UserRole = 'viewer' | 'editor' | 'admin'

export interface User {
  id: string
  username: string
  role: UserRole
  token: string
}

const STORAGE_KEY = 'auth_user'

const user = ref<User | null>(null)
const isLoading = ref(false)
const error = ref<string | null>(null)

// Load from localStorage on init
const savedUser = localStorage.getItem(STORAGE_KEY)
if (savedUser) {
  try {
    user.value = JSON.parse(savedUser)
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
}

export function useAuth() {
  const router = useRouter()

  const isAuthenticated = computed(() => !!user.value)
  const currentUser = computed(() => user.value)
  const role = computed(() => user.value?.role ?? null)
  
  const isViewer = computed(() => user.value?.role === 'viewer')
  const isEditor = computed(() => user.value?.role === 'editor')
  const isAdmin = computed(() => user.value?.role === 'admin')

  const canUpload = computed(() => 
    user.value ? ['editor', 'admin'].includes(user.value.role) : false
  )
  const canDelete = computed(() => user.value?.role === 'admin')
  const canApprove = computed(() => user.value?.role === 'admin')

  /**
   * Login user with credentials
   * In production, this would call the backend API
   * For now, simulating authentication with role-based access
   */
  const login = async (username: string, password: string, selectedRole: UserRole = 'editor'): Promise<boolean> => {
    isLoading.value = true
    error.value = null

    try {
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 500))

      // Simple validation (in production, this would be a real API call)
      if (!username || !password) {
        error.value = 'Username and password are required'
        return false
      }

      if (password.length < 3) {
        error.value = 'Invalid credentials'
        return false
      }

      // Create user session
      const newUser: User = {
        id: `user_${Date.now()}`,
        username: username.trim(),
        role: selectedRole,
        token: `mock_token_${Date.now()}_${selectedRole}`,
      }

      user.value = newUser
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newUser))
      
      return true
    } catch (err) {
      error.value = 'Login failed. Please try again.'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Logout user and clear session
   */
  const logout = () => {
    user.value = null
    localStorage.removeItem(STORAGE_KEY)
    router.push('/login')
  }

  /**
   * Get auth headers for API requests
   */
  const getAuthHeaders = (): Record<string, string> => {
    const headers: Record<string, string> = {}
    
    if (user.value) {
      // Send role header for backend authorization
      headers['X-User-Role'] = user.value.role
      // In production, you'd also send: Authorization: `Bearer ${user.value.token}`
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
   * Update user role (for role switching in settings)
   */
  const updateRole = (newRole: UserRole) => {
    if (user.value) {
      user.value.role = newRole
      user.value.token = `mock_token_${Date.now()}_${newRole}`
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user.value))
    }
  }

  return {
    // State
    user: currentUser,
    isLoading,
    error,
    
    // Computed
    isAuthenticated,
    role,
    isViewer,
    isEditor,
    isAdmin,
    canUpload,
    canDelete,
    canApprove,
    
    // Methods
    login,
    logout,
    getAuthHeaders,
    hasRole,
    updateRole,
  }
}
