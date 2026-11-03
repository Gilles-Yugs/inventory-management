<template>
  <svg
    class="nav-icon"
    xmlns="http://www.w3.org/2000/svg"
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.75"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <!-- Decorative only: the accessible name always comes from the link/button text -->
    <template v-if="name === 'overview'">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </template>
    <template v-else-if="name === 'inventory'">
      <path d="M21 8l-9-5-9 5 9 5 9-5z" />
      <path d="M3 8v8l9 5 9-5V8" />
      <path d="M12 13v8" />
    </template>
    <template v-else-if="name === 'orders'">
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </template>
    <template v-else-if="name === 'finance'">
      <path d="M3 17l5-5 4 4 8-9" />
      <path d="M15 7h5v5" />
    </template>
    <template v-else-if="name === 'demand'">
      <path d="M4 20V10M10 20V4M16 20v-8M22 20H2" />
    </template>
    <template v-else-if="name === 'restocking'">
      <path d="M20 12a8 8 0 01-14.5 4.7" />
      <path d="M4 12A8 8 0 0118.5 7.3" />
      <path d="M18.5 3v4.3h-4.3M5.5 21v-4.3h4.3" />
    </template>
    <template v-else-if="name === 'reports'">
      <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h6" />
    </template>
    <template v-else-if="name === 'logo'">
      <path d="M12 2l9 5v10l-9 5-9-5V7l9-5z" />
      <path d="M12 12l9-5M12 12L3 7M12 12v10" />
    </template>
    <template v-else-if="name === 'menu'">
      <path d="M4 6h16M4 12h16M4 18h16" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="M6 6l12 12M18 6L6 18" />
    </template>
    <template v-else-if="name === 'chevron-left'">
      <path d="M15 6l-6 6 6 6" />
    </template>
  </svg>
</template>

<script setup>
defineProps({
  name: {
    type: String,
    required: true
  }
})
</script>

<style scoped>
.nav-icon {
  flex-shrink: 0;
}
</style>
