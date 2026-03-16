import { ref, computed } from 'vue'

export type UserRole = 'viewer' | 'editor' | 'admin'

const STORAGE_KEY = 'dev_user_role'

const currentRole = ref<UserRole>('editor')

// Load from localStorage on init
const savedRole = localStorage.getItem(STORAGE_KEY)
if (savedRole && ['viewer', 'editor', 'admin'].includes(savedRole)) {
  currentRole.value = savedRole as UserRole
}

export function useAuth() {
  const setRole = (role: UserRole) => {
    currentRole.value = role
    localStorage.setItem(STORAGE_KEY, role)
  }

  const getRoleHeader = () => currentRole.value

  const isViewer = computed(() => currentRole.value === 'viewer')
  const isEditor = computed(() => currentRole.value === 'editor')
  const isAdmin = computed(() => currentRole.value === 'admin')

  const canUpload = computed(() => ['editor', 'admin'].includes(currentRole.value))
  const canDelete = computed(() => currentRole.value === 'admin')
  const canApprove = computed(() => currentRole.value === 'admin')

  return {
    role: computed(() => currentRole.value),
    setRole,
    getRoleHeader,
    isViewer,
    isEditor,
    isAdmin,
    canUpload,
    canDelete,
    canApprove,
  }
}
