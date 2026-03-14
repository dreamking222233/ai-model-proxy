<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
:root {
  --primary-color: #667eea;
  --primary-dark: #764ba2;
  --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --primary-gradient-hover: linear-gradient(135deg, #7b8ff0 0%, #8a5fb5 100%);
  --card-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  --card-hover-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
  --card-radius: 12px;
  --transition-normal: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  --sidebar-bg-start: #1a1a2e;
  --sidebar-bg-end: #16213e;
  --success-color: #52c41a;
  --warning-color: #fa8c16;
  --error-color: #f5222d;
  --bg-color: #f0f2f5;
  --text-primary: #1a1a2e;
  --text-secondary: #8c8c8c;
}

#app {
  height: 100%;
}

/* Global utility classes */
.gradient-text {
  background: var(--primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

</style>
