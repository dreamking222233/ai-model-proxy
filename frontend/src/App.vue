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
/* Import Animate.css globally */
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

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
  --transition-normal: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
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
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
  overflow: hidden;
  filter: blur(100px);
  opacity: 1;
  pointer-events: none;
}

.global-aurora-bg .blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
}

.global-aurora-bg .blob-1 {
  width: 600px;
  height: 600px;
  background: rgba(102, 126, 234, 0.4);
  top: -150px;
  left: -150px;
  animation: aurora-move-1 25s infinite alternate ease-in-out;
}

.global-aurora-bg .blob-2 {
  width: 500px;
  height: 500px;
  background: rgba(54, 207, 201, 0.35);
  bottom: -100px;
  right: -100px;
  animation: aurora-move-2 30s infinite alternate-reverse ease-in-out;
}

.global-aurora-bg .blob-3 {
  width: 400px;
  height: 400px;
  background: rgba(250, 140, 22, 0.25);
  top: 40%;
  right: 15%;
  animation: aurora-move-3 22s infinite alternate ease-in-out;
}

@keyframes aurora-move-1 {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(100px, 150px) scale(1.2); }
}

@keyframes aurora-move-2 {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(-120px, -80px) scale(1.1); }
}

@keyframes aurora-move-3 {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(-50px, 120px) scale(1.3); }
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

</style>
