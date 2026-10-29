<template>
  <div class="sa-panel">
    <header class="sa-header">
      <div class="sa-brand">
        <div class="sa-logo"><i class="fas fa-shield-halved"></i></div>
        <div>
          <h2>超级管理后台</h2>
          <span>NovaChat 平台运营与治理中心</span>
        </div>
      </div>
      <div class="sa-user">
        <span class="sa-role-badge">超级管理员</span>
        <span class="sa-username">{{ authStore.currentUser?.username }}</span>
        <button class="sa-back" @click="onLogout"><i class="fas fa-right-from-bracket"></i> 退出登录</button>
      </div>
    </header>

    <nav class="sa-nav">
      <button :class="['sa-nav-btn', { active: tab === 'dashboard' }]" @click="tab = 'dashboard'">
        <i class="fas fa-chart-line"></i> 数据面板
      </button>
      <button :class="['sa-nav-btn', { active: tab === 'users' }]" @click="tab = 'users'">
        <i class="fas fa-users-cog"></i> 用户管理
      </button>
      <button :class="['sa-nav-btn', { active: tab === 'models' }]" @click="tab = 'models'">
        <i class="fas fa-sliders"></i> 模型配置
      </button>
      <button :class="['sa-nav-btn', { active: tab === 'audit' }]" @click="tab = 'audit'">
        <i class="fas fa-clipboard-list"></i> 安全审计
      </button>
      <button :class="['sa-nav-btn', { active: tab === 'docs' }]" @click="tab = 'docs'">
        <i class="fas fa-folder-open"></i> 文档管理
      </button>
    </nav>

    <main class="sa-content">
      <DashboardView v-if="tab === 'dashboard'" />
      <UserManagement v-else-if="tab === 'users'" />
      <ModelConfigView v-else-if="tab === 'models'" />
      <AuditLogView v-else-if="tab === 'audit'" />
      <DocumentSettings v-else-if="tab === 'docs'" embedded />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useAuthStore } from '@/stores/auth';
import DashboardView from './DashboardView.vue';
import UserManagement from './UserManagement.vue';
import ModelConfigView from './ModelConfigView.vue';
import AuditLogView from './AuditLogView.vue';
import DocumentSettings from '@/components/Documents/DocumentSettings.vue';

const authStore = useAuthStore();
const tab = ref<'dashboard' | 'users' | 'models' | 'audit' | 'docs'>('dashboard');

const onLogout = () => {
  if (confirm('确定退出登录吗？')) {
    authStore.handleLogout();
  }
};
</script>

<style scoped>
/* 铺满可用视口：移动端全屏，桌面端居中限宽，任何尺寸下都不会出现横向溢出 */
.sa-panel {
  /* 浅色主题：仅在超级管理台子树内覆盖主题变量，主应用不受影响 */
  --bg-color: #f3f7fc; /* 内容区浅底 */
  --sidebar-bg: #ffffff; /* 顶栏浅底 */
  --text-color: #1e2a3a; /* 主文字（深石板灰，浅底高对比） */
  --text-light: #5a6b7f; /* 次要文字（仍满足可读对比） */
  --white: #ffffff; /* 卡片/表面 */
  --primary-color: #2563eb; /* 主色（白底与白字双向可读） */
  --primary-light: #93c5fd; /* 渐变亮色 */
  --border-color: #e3eaf3; /* 浅描边 */
  --shadow: 0 10px 28px rgba(23, 70, 130, 0.1), 0 2px 6px rgba(23, 70, 130, 0.06);
  width: 100%;
  height: 100%;
  max-width: none;
  margin: 0;
  background: #ffffff;
  color: var(--text-color);
  border: 0;
  border-radius: 0;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.sa-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #ffffff 0%, #eef5ff 100%);
  border-bottom: 1px solid var(--border-color);
}
.sa-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.sa-logo {
  flex: 0 0 auto;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: #eef4ff;
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  color: var(--primary-color);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.12);
}
.sa-brand h2 {
  font-family: 'Zcool KuaiLe', cursive;
  color: var(--primary-color);
  font-size: clamp(1.1rem, 2.4vw, 1.5rem);
  line-height: 1.2;
}
.sa-brand span {
  display: block;
  font-size: 0.78rem;
  color: var(--text-light);
}
.sa-user {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.sa-role-badge {
  background: #ffe9e6;
  color: #c0392b;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 0.78rem;
  font-weight: 600;
  white-space: nowrap;
}
.sa-username {
  font-weight: 700;
  color: var(--text-color);
  max-width: 40vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-back {
  border: 1px solid var(--border-color);
  background: #ffffff;
  color: var(--primary-color);
  border-radius: 14px;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.1);
  white-space: nowrap;
  transition: var(--transition);
}
.sa-back:hover {
  background: #eef4ff;
}
/* 标签栏在窄屏可横向滚动，不挤压、不换行溢出 */
.sa-nav {
  display: flex;
  gap: 8px;
  padding: 12px 16px 0;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.sa-nav::-webkit-scrollbar {
  display: none;
}
.sa-nav-btn {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  color: var(--text-color);
  font-weight: 600;
  padding: 10px 16px;
  border-radius: 15px 15px 0 0;
  cursor: pointer;
  transition: var(--transition);
  white-space: nowrap;
}
.sa-nav-btn.active {
  background: #e8f1ff;
  color: var(--primary-color);
  box-shadow: inset 0 -2px 0 var(--primary-color);
}
.sa-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 18px 20px;
  background: var(--bg-color);
}

/* 桌面端与主应用一致：居中并限制最大宽度 */
@media (min-width: 900px) {
  .sa-panel {
    width: min(100%, 1120px);
    margin: 0 auto;
    border-left: 1px solid var(--nova-border, rgba(90, 171, 255, 0.22));
    border-right: 1px solid var(--nova-border, rgba(90, 171, 255, 0.22));
  }
}

@media (max-width: 640px) {
  .sa-header {
    padding: 12px;
    gap: 10px;
  }
  .sa-brand {
    gap: 10px;
  }
  .sa-logo {
    width: 38px;
    height: 38px;
    font-size: 1.15rem;
  }
  .sa-brand h2 {
    font-size: 1.1rem;
  }
  .sa-brand span {
    font-size: 0.7rem;
  }
  .sa-role-badge {
    display: none;
  }
  .sa-username {
    max-width: 34vw;
    font-size: 0.9rem;
  }
  .sa-back {
    padding: 7px 10px;
    font-size: 0.85rem;
  }
  .sa-nav {
    padding: 10px 10px 0;
    gap: 6px;
  }
  .sa-nav-btn {
    padding: 9px 12px;
    font-size: 0.88rem;
  }
  .sa-content {
    padding: 12px 10px 20px;
  }
}
</style>
