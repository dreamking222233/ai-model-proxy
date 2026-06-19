<template>
  <div id="app">
    <!-- Global Aurora Background -->
    <div class="global-aurora-bg">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
    </div>
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
  --card-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
  --card-hover-shadow: 0 12px 40px rgba(102, 126, 234, 0.12);
  --glass-bg: rgba(255, 255, 255, 0.7);
  --glass-border: rgba(255, 255, 255, 0.6);
  --card-radius: 16px;
  --transition-normal: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  --sidebar-bg-start: #0d0d1a;
  --sidebar-bg-end: #0f1225;
  --success-color: #52c41a;
  --warning-color: #fa8c16;
  --error-color: #f5222d;
  --bg-color: transparent; /* Changed to transparent for global bg */
  --text-primary: #1a1a2e;
  --text-secondary: #8c8c8c;
}

#app {
  height: 100%;
  position: relative;
}

/* Global Aurora Background Styles */
.global-aurora-bg {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: -1;
  background:
    radial-gradient(circle at 12% 8%, rgba(102, 126, 234, 0.14), transparent 30%),
    radial-gradient(circle at 88% 16%, rgba(54, 207, 201, 0.12), transparent 28%),
    radial-gradient(circle at 72% 78%, rgba(250, 140, 22, 0.08), transparent 26%),
    linear-gradient(135deg, #f7f9fc 0%, #edf1f7 100%);
  overflow: hidden;
  opacity: 1;
  pointer-events: none;
}

.global-aurora-bg .blob {
  display: none;
}

/* Global utility classes */
.gradient-text {
  background: var(--primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Override Ant Design default layout backgrounds */
.ant-layout, .ant-layout-header, .ant-layout-content, .ant-layout-sider {
  background: transparent !important;
}

body {
  margin: 0;
  background-color: #f8fafc; /* 底层保底色 */
}

/* Lightweight local replacement for the Animate.css classes used by user pages. */
.animate__animated {
  animation-duration: 0.24s;
  animation-fill-mode: both;
}

.animate__fadeIn,
.animate__fadeInUp,
.animate__fadeInDown,
.animate__fadeInLeft,
.animate__fadeInRight {
  animation-name: codex-fade-in;
}

@keyframes codex-fade-in {
  from { opacity: 0; transform: translate3d(0, 4px, 0); }
  to { opacity: 1; transform: translate3d(0, 0, 0); }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation: none !important;
    animation-delay: 0ms !important;
    scroll-behavior: auto !important;
    transition-duration: 0.001ms !important;
  }
}

</style>
