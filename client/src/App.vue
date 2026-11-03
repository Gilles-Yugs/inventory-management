<template>
  <div class="app" :class="layoutClass">
    <!-- Backdrop only exists in the off-canvas (<=640px) state; click closes the drawer -->
    <div
      v-if="isMobile && drawerOpen"
      class="sidebar-backdrop"
      aria-hidden="true"
      @click="closeDrawer"
    ></div>

    <aside id="app-sidebar" class="sidebar" :aria-label="t('nav.mainNavigation')">
      <div class="sidebar-header">
        <div class="logo">
          <NavIcon name="logo" class="logo-mark" />
          <div class="logo-text" :class="{ 'sr-only': isCollapsed }">
            <h1>{{ t('nav.companyName') }}</h1>
            <span class="subtitle">{{ t('nav.subtitle') }}</span>
          </div>
        </div>
      </div>

      <nav class="sidebar-nav">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: $route.path === item.to }"
          :title="isCollapsed ? t(item.labelKey) : null"
          :aria-label="isCollapsed ? t(item.labelKey) : null"
        >
          <NavIcon :name="item.icon" />
          <span class="nav-label" :class="{ 'sr-only': isCollapsed }">{{ t(item.labelKey) }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <button
          type="button"
          class="sidebar-toggle"
          :aria-expanded="isMobile ? drawerOpen : !isCollapsed"
          aria-controls="app-sidebar"
          :aria-label="toggleLabel"
          :title="toggleLabel"
          @click="onToggleClick"
        >
          <NavIcon :name="isMobile ? 'close' : 'chevron-left'" class="toggle-icon" />
          <span class="nav-label" :class="{ 'sr-only': isCollapsed }">{{ toggleLabel }}</span>
        </button>
      </div>
    </aside>

    <div class="app-body">
      <header class="top-bar">
        <button
          type="button"
          class="menu-button"
          :aria-expanded="drawerOpen"
          aria-controls="app-sidebar"
          :aria-label="t('nav.openMenu')"
          :title="t('nav.openMenu')"
          @click="openDrawer"
        >
          <NavIcon name="menu" />
        </button>
        <div class="top-bar-actions">
          <LanguageSwitcher />
          <ProfileMenu
            @show-profile-details="showProfileDetails = true"
            @show-tasks="showTasks = true"
          />
        </div>
      </header>
      <FilterBar />
      <main class="main-content">
        <router-view />
      </main>
    </div>

    <ProfileDetailsModal
      :is-open="showProfileDetails"
      @close="showProfileDetails = false"
    />

    <TasksModal
      :is-open="showTasks"
      :tasks="tasks"
      @close="showTasks = false"
      @add-task="addTask"
      @delete-task="deleteTask"
      @toggle-task="toggleTask"
    />
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from './api'
import { useAuth } from './composables/useAuth'
import { useI18n } from './composables/useI18n'
import FilterBar from './components/FilterBar.vue'
import ProfileMenu from './components/ProfileMenu.vue'
import ProfileDetailsModal from './components/ProfileDetailsModal.vue'
import TasksModal from './components/TasksModal.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'
import NavIcon from './components/NavIcon.vue'

// Breakpoints: <=640px off-canvas, 641-1023px icons-only default, >=1024px expanded default
const MOBILE_QUERY = '(max-width: 640px)'
const TABLET_QUERY = '(max-width: 1023px)'
const STORAGE_KEY = 'sidebar-collapsed'

const NAV_ITEMS = [
  { to: '/', labelKey: 'nav.overview', icon: 'overview' },
  { to: '/inventory', labelKey: 'nav.inventory', icon: 'inventory' },
  { to: '/orders', labelKey: 'nav.orders', icon: 'orders' },
  { to: '/spending', labelKey: 'nav.finance', icon: 'finance' },
  { to: '/demand', labelKey: 'nav.demandForecast', icon: 'demand' },
  { to: '/restocking', labelKey: 'nav.restocking', icon: 'restocking' },
  { to: '/reports', labelKey: 'nav.reports', icon: 'reports' }
]

// localStorage can throw (private mode, blocked storage, quota); the UI must still render,
// so every access is guarded and falls back to "no stored preference".
const readStoredCollapsed = () => {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value === null ? null : value === 'true'
  } catch (err) {
    return null
  }
}

const writeStoredCollapsed = (value) => {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(value))
  } catch (err) {
    // Ignore: preference simply will not persist
  }
}

export default {
  name: 'App',
  components: {
    FilterBar,
    ProfileMenu,
    ProfileDetailsModal,
    TasksModal,
    LanguageSwitcher,
    NavIcon
  },
  setup() {
    const { currentUser } = useAuth()
    const { t } = useI18n()
    const route = useRoute()

    // --- Sidebar state ---
    // viewport: 'mobile' | 'tablet' | 'desktop'. Derived from matchMedia, not window.innerWidth,
    // so it matches the CSS media queries exactly.
    const viewport = ref('desktop')
    const collapsed = ref(false) // icons-only; meaningful on tablet/desktop only
    const drawerOpen = ref(false) // off-canvas open; meaningful on mobile only

    const isMobile = computed(() => viewport.value === 'mobile')
    // On mobile the drawer always shows full labels, so never treat it as collapsed
    const isCollapsed = computed(() => !isMobile.value && collapsed.value)

    const layoutClass = computed(() => ({
      'sidebar-collapsed': isCollapsed.value,
      'sidebar-mobile': isMobile.value,
      'sidebar-open': isMobile.value && drawerOpen.value
    }))

    const toggleLabel = computed(() => {
      if (isMobile.value) return t('nav.closeMenu')
      return isCollapsed.value ? t('nav.expandSidebar') : t('nav.collapseSidebar')
    })

    const detectViewport = () => {
      if (typeof window === 'undefined' || !window.matchMedia) return 'desktop'
      if (window.matchMedia(MOBILE_QUERY).matches) return 'mobile'
      if (window.matchMedia(TABLET_QUERY).matches) return 'tablet'
      return 'desktop'
    }

    // Apply the default for a range. Called on mount and ONLY when a breakpoint is crossed,
    // so a manual toggle sticks while the viewport stays within the same range, and is
    // reset to that range's default (or stored desktop choice) once the user crosses over.
    const applyViewportDefaults = (next) => {
      viewport.value = next
      drawerOpen.value = false
      if (next === 'tablet') {
        collapsed.value = true
      } else if (next === 'desktop') {
        const stored = readStoredCollapsed()
        collapsed.value = stored === null ? false : stored
      }
    }

    let mobileMql = null
    let tabletMql = null
    const onBreakpointChange = () => {
      const next = detectViewport()
      if (next !== viewport.value) applyViewportDefaults(next)
    }

    const openDrawer = () => {
      drawerOpen.value = true
    }
    const closeDrawer = () => {
      drawerOpen.value = false
    }

    const onToggleClick = () => {
      if (isMobile.value) {
        closeDrawer()
        return
      }
      collapsed.value = !collapsed.value
      // Only the desktop choice is persisted; tablet always starts icons-only
      if (viewport.value === 'desktop') writeStoredCollapsed(collapsed.value)
    }

    const onKeydown = (event) => {
      if (event.key === 'Escape' && drawerOpen.value) closeDrawer()
    }

    // Close the drawer after navigating (link click or browser back/forward)
    watch(() => route.path, closeDrawer)

    // Compute the initial state synchronously in setup so the first render is correct
    // (avoids a flash of the wrong layout)
    applyViewportDefaults(detectViewport())

    onMounted(() => {
      if (window.matchMedia) {
        mobileMql = window.matchMedia(MOBILE_QUERY)
        tabletMql = window.matchMedia(TABLET_QUERY)
        mobileMql.addEventListener('change', onBreakpointChange)
        tabletMql.addEventListener('change', onBreakpointChange)
      }
      window.addEventListener('keydown', onKeydown)
    })

    onBeforeUnmount(() => {
      if (mobileMql) mobileMql.removeEventListener('change', onBreakpointChange)
      if (tabletMql) tabletMql.removeEventListener('change', onBreakpointChange)
      window.removeEventListener('keydown', onKeydown)
    })

    const showProfileDetails = ref(false)
    const showTasks = ref(false)
    const apiTasks = ref([])

    // Merge mock tasks from currentUser with API tasks
    const tasks = computed(() => {
      return [...currentUser.value.tasks, ...apiTasks.value]
    })

    const loadTasks = async () => {
      try {
        apiTasks.value = await api.getTasks()
      } catch (err) {
        console.error('Failed to load tasks:', err)
      }
    }

    const addTask = async (taskData) => {
      try {
        const newTask = await api.createTask(taskData)
        // Add new task to the beginning of the array
        apiTasks.value.unshift(newTask)
      } catch (err) {
        console.error('Failed to add task:', err)
      }
    }

    const deleteTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const isMockTask = currentUser.value.tasks.some(t => t.id === taskId)

        if (isMockTask) {
          // Remove from mock tasks
          const index = currentUser.value.tasks.findIndex(t => t.id === taskId)
          if (index !== -1) {
            currentUser.value.tasks.splice(index, 1)
          }
        } else {
          // Remove from API tasks
          await api.deleteTask(taskId)
          apiTasks.value = apiTasks.value.filter(t => t.id !== taskId)
        }
      } catch (err) {
        console.error('Failed to delete task:', err)
      }
    }

    const toggleTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const mockTask = currentUser.value.tasks.find(t => t.id === taskId)

        if (mockTask) {
          // Toggle mock task status
          mockTask.status = mockTask.status === 'pending' ? 'completed' : 'pending'
        } else {
          // Toggle API task
          const updatedTask = await api.toggleTask(taskId)
          const index = apiTasks.value.findIndex(t => t.id === taskId)
          if (index !== -1) {
            apiTasks.value[index] = updatedTask
          }
        }
      } catch (err) {
        console.error('Failed to toggle task:', err)
      }
    }

    onMounted(loadTasks)

    return {
      t,
      navItems: NAV_ITEMS,
      isMobile,
      isCollapsed,
      drawerOpen,
      layoutClass,
      toggleLabel,
      openDrawer,
      closeDrawer,
      onToggleClick,
      showProfileDetails,
      showTasks,
      tasks,
      addTask,
      deleteTask,
      toggleTask
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: #f8fafc;
  color: #1e293b;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/*
 * Layout: fixed sidebar + app-body column (top bar, FilterBar, page content).
 * --sidebar-width drives both the sidebar width and the content offset so they
 * animate together. Heights: top bar is 70px; FilterBar's sticky `top: 70px`
 * depends on that, keep them in sync.
 */
.app {
  --sidebar-width: 240px;
  min-height: 100vh;
}

.app.sidebar-collapsed {
  --sidebar-width: 64px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.sidebar {
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
  z-index: 200;
  overflow-x: hidden;
  overflow-y: auto;
  transition: width 0.2s ease, transform 0.2s ease, visibility 0s linear 0s;
}

.sidebar-header {
  display: flex;
  align-items: center;
  height: 70px;
  padding: 0 1.25rem;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
}

.logo-mark {
  width: 24px;
  height: 24px;
  color: #2563eb;
}

.logo-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.logo h1 {
  font-size: 1rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.subtitle {
  font-size: 0.75rem;
  color: #64748b;
  font-weight: 400;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem;
  flex: 1;
}

.nav-link,
.sidebar-toggle {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.625rem;
  color: #64748b;
  text-decoration: none;
  font-family: inherit;
  font-weight: 500;
  font-size: 0.938rem;
  border-radius: 6px;
  transition: color 0.2s ease, background-color 0.2s ease;
}

.nav-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-link:hover,
.sidebar-toggle:hover {
  color: #0f172a;
  background: #f1f5f9;
}

.nav-link.active {
  color: #2563eb;
  background: #eff6ff;
  box-shadow: inset 3px 0 0 #2563eb;
}

.nav-link:focus-visible,
.sidebar-toggle:focus-visible,
.menu-button:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: -2px;
}

.sidebar-footer {
  padding: 0.75rem;
  border-top: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.sidebar-toggle {
  background: none;
  border: none;
  cursor: pointer;
}

.toggle-icon {
  transition: transform 0.2s ease;
}

.sidebar-collapsed .toggle-icon {
  transform: rotate(180deg);
}

.sidebar-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 190;
}

.app-body {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  /* min-width: 0 lets wide tables/filters shrink instead of stretching the page */
  min-width: 0;
  margin-left: var(--sidebar-width);
  transition: margin-left 0.2s ease;
}

.top-bar {
  display: flex;
  align-items: center;
  height: 70px;
  padding: 0 2rem;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
  position: sticky;
  top: 0;
  z-index: 100;
}

.top-bar-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-left: auto;
}

.menu-button {
  display: none;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #334155;
  cursor: pointer;
  transition: all 0.2s ease;
}

.menu-button:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.main-content {
  flex: 1;
  max-width: 1600px;
  width: 100%;
  margin: 0 auto;
  padding: 1.5rem 2rem;
}


/* Off-canvas drawer (<=640px). Keep in sync with MOBILE_QUERY in the script. */
@media (max-width: 640px) {
  .app-body {
    margin-left: 0;
  }

  .sidebar {
    width: 240px;
    transform: translateX(-100%);
    /* visibility hides the closed drawer's links from keyboard/AT; delayed so the slide-out finishes first */
    visibility: hidden;
    transition: transform 0.2s ease, visibility 0s linear 0.2s;
  }

  .sidebar-open .sidebar {
    transform: translateX(0);
    visibility: visible;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
    transition: transform 0.2s ease, visibility 0s linear 0s;
  }

  .top-bar {
    padding: 0 1rem;
  }

  .menu-button {
    display: inline-flex;
  }

  .top-bar-actions {
    gap: 0.5rem;
  }

  /* Keep the top bar from overflowing on narrow phones: icon/avatar only */
  .top-bar .profile-name,
  .top-bar .language-label {
    display: none;
  }

  .main-content {
    padding: 1rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .sidebar,
  .app-body,
  .toggle-icon,
  .nav-link,
  .sidebar-toggle {
    transition: none;
  }
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  font-size: 1.875rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 0.375rem;
  letter-spacing: -0.025em;
}

.page-header p {
  color: #64748b;
  font-size: 0.938rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: white;
  padding: 1.25rem;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
}

.stat-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.stat-label {
  color: #64748b;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.625rem;
}

.stat-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.stat-card.warning .stat-value {
  color: #ea580c;
}

.stat-card.success .stat-value {
  color: #059669;
}

.stat-card.danger .stat-value {
  color: #dc2626;
}

.stat-card.info .stat-value {
  color: #2563eb;
}

.card {
  background: white;
  border-radius: 10px;
  padding: 1.25rem;
  border: 1px solid #e2e8f0;
  margin-bottom: 1.25rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.875rem;
  border-bottom: 1px solid #e2e8f0;
}

.card-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
}

th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  font-weight: 600;
  color: #475569;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

td {
  padding: 0.5rem 0.75rem;
  border-top: 1px solid #f1f5f9;
  color: #334155;
  font-size: 0.875rem;
}

tbody tr {
  transition: background-color 0.15s ease;
}

tbody tr:hover {
  background: #f8fafc;
}

.badge {
  display: inline-block;
  padding: 0.313rem 0.75rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.badge.success {
  background: #d1fae5;
  color: #065f46;
}

.badge.warning {
  background: #fed7aa;
  color: #92400e;
}

.badge.danger {
  background: #fecaca;
  color: #991b1b;
}

.badge.info {
  background: #dbeafe;
  color: #1e40af;
}

.badge.increasing {
  background: #d1fae5;
  color: #065f46;
}

.badge.decreasing {
  background: #fecaca;
  color: #991b1b;
}

.badge.stable {
  background: #e0e7ff;
  color: #3730a3;
}

.badge.high {
  background: #fecaca;
  color: #991b1b;
}

.badge.medium {
  background: #fed7aa;
  color: #92400e;
}

.badge.low {
  background: #dbeafe;
  color: #1e40af;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: #64748b;
  font-size: 0.938rem;
}

.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 1rem;
  border-radius: 8px;
  margin: 1rem 0;
  font-size: 0.938rem;
}
</style>
