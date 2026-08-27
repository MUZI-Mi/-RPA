<template>
  <div class="layout">
    <!-- 豆包风格侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-top">
        <div class="logo">
          <div class="logo-icon">
            <el-icon><MagicStick /></el-icon>
          </div>
          <span class="logo-text">智简灵析</span>
        </div>
        <button class="new-chat-btn" @click="$router.push('/')">
          <el-icon><Plus /></el-icon>
          <span>新建任务</span>
        </button>
      </div>

      <nav class="nav">
        <div class="nav-group-title">功能</div>
        <a
          v-for="item in navItems"
          :key="item.path"
          class="nav-item"
          :class="{ active: activeMenu === item.path }"
          @click="$router.push(item.path)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </a>
      </nav>

      <div class="sidebar-bottom">
        <div class="version-tip">
          <el-icon><InfoFilled /></el-icon>
          <span>本地运行 · 数据不上云</span>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const activeMenu = computed(() => {
  if (route.path.startsWith("/report")) return "/tasks";
  return route.path;
});

const navItems = [
  { path: "/", label: "指令输入", icon: "ChatLineSquare" },
  { path: "/tasks", label: "任务管理", icon: "List" },
  { path: "/settings", label: "设置", icon: "Setting" },
];
</script>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ===== 侧边栏 ===== */
.sidebar {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #f7f8fa;
  border-right: 1px solid var(--db-border);
  padding: 16px 12px;
}

.sidebar-top {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #2e6ef5, #6b9bf8);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  box-shadow: 0 2px 8px rgba(46, 110, 245, 0.3);
}

.logo-text {
  font-size: 17px;
  font-weight: 600;
  color: var(--db-text);
  letter-spacing: 1px;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 40px;
  border-radius: 12px;
  border: 1px solid var(--db-border);
  background: #fff;
  color: var(--db-text);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}
.new-chat-btn:hover {
  border-color: var(--db-primary);
  color: var(--db-primary);
  box-shadow: var(--db-shadow-hover);
}

/* ===== 导航 ===== */
.nav {
  flex: 1;
  margin-top: 20px;
  overflow-y: auto;
}

.nav-group-title {
  font-size: 12px;
  color: var(--db-text-muted);
  padding: 0 10px 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  color: var(--db-text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}
.nav-item:hover {
  background: #eceef1;
  color: var(--db-text);
}
.nav-item.active {
  background: var(--db-primary-light);
  color: var(--db-primary);
  font-weight: 500;
}
.nav-item .el-icon {
  font-size: 17px;
}

/* ===== 底部 ===== */
.sidebar-bottom {
  padding-top: 12px;
  border-top: 1px solid var(--db-border);
}
.version-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--db-text-muted);
  padding: 0 8px;
}

/* ===== 主内容区 ===== */
.main {
  flex: 1;
  overflow-y: auto;
  background: var(--db-bg);
}
</style>
