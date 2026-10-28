<template>
  <div class="dashboard">
    <div class="section-title">
      <h3><i class="fas fa-chart-line"></i> 关键业务指标</h3>
      <button class="btn-refresh" :disabled="store.metricsLoading" @click="store.fetchMetrics()">
        <i class="fas fa-sync" :class="{ 'fa-spin': store.metricsLoading }"></i> 刷新
      </button>
    </div>

    <div v-if="store.metricsLoading && !store.metrics" class="loading-box">加载中...</div>

    <template v-else-if="store.metrics">
      <!-- 指标卡片 -->
      <div class="stat-grid">
        <div class="stat-card" v-for="card in statCards" :key="card.label">
          <div class="stat-icon" :style="{ color: card.color }"><i :class="card.icon"></i></div>
          <div class="stat-body">
            <div class="stat-value">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
        </div>
      </div>

      <!-- 趋势图 -->
      <div class="charts">
        <div class="chart-card">
          <h4><i class="fas fa-user-plus"></i> 近 7 天注册趋势</h4>
          <div v-if="hasData(store.metrics.registrations_last_7_days)" class="bars">
            <div class="bar-item" v-for="p in store.metrics.registrations_last_7_days" :key="p.date">
              <div class="bar" :style="{ height: barHeight(p.count, registMax) + '%' }">
                <span class="bar-num">{{ p.count }}</span>
              </div>
              <div class="bar-label">{{ shortDate(p.date) }}</div>
            </div>
          </div>
          <div v-else class="empty-mini"><i class="fas fa-inbox"></i><p>近 7 天暂无新注册</p></div>
        </div>

        <div class="chart-card">
          <h4><i class="fas fa-sign-in-alt"></i> 近 7 天登录趋势</h4>
          <div v-if="hasData(store.metrics.logins_last_7_days)" class="bars">
            <div class="bar-item" v-for="p in store.metrics.logins_last_7_days" :key="p.date">
              <div class="bar bar-alt" :style="{ height: barHeight(p.count, loginMax) + '%' }">
                <span class="bar-num">{{ p.count }}</span>
              </div>
              <div class="bar-label">{{ shortDate(p.date) }}</div>
            </div>
          </div>
          <div v-else class="empty-mini"><i class="fas fa-inbox"></i><p>近 7 天暂无登录记录</p></div>
        </div>
      </div>

      <!-- 角色分布 -->
      <div class="chart-card">
        <h4><i class="fas fa-users-cog"></i> 角色分布</h4>
        <div v-if="store.metrics.role_distribution.length" class="dist">
          <div class="dist-row" v-for="r in store.metrics.role_distribution" :key="r.role">
            <div class="dist-label">{{ roleLabel(r.role) }}</div>
            <div class="dist-track">
              <div class="dist-fill" :style="{ width: distWidth(r.count) + '%' }"></div>
            </div>
            <div class="dist-count">{{ r.count }}</div>
          </div>
        </div>
        <div v-else class="empty-mini"><i class="fas fa-inbox"></i><p>暂无角色数据</p></div>
      </div>
    </template>

    <div v-else class="empty-box">
      <i class="fas fa-exclamation-circle"></i>
      <p>面板数据加载失败，请稍后重试</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useSuperAdminStore } from '@/stores/superAdmin';
import { ROLE_LABELS } from '@/stores/superAdmin';
import type { UserRole } from '@/types/user';

const store = useSuperAdminStore();

const statCards = computed(() => {
  const m = store.metrics!;
  return [
    { label: '用户总数', value: m.total_users, icon: 'fas fa-users', color: '#ff9e99' },
    { label: '启用中', value: m.active_users, icon: 'fas fa-user-check', color: '#7bc47f' },
    { label: '已禁用', value: m.disabled_users, icon: 'fas fa-user-slash', color: '#e57373' },
    { label: '管理员', value: m.admin_users, icon: 'fas fa-user-shield', color: '#6fa8dc' },
    { label: '会话总数', value: m.total_sessions, icon: 'fas fa-comments', color: '#ba9fd6' },
    { label: '消息总数', value: m.total_messages, icon: 'fas fa-envelope', color: '#f6b26b' },
    { label: '知识库文档', value: m.total_documents, icon: 'fas fa-database', color: '#76c7c0' },
  ];
});

const registMax = computed(() =>
  Math.max(1, ...(store.metrics?.registrations_last_7_days.map((p) => p.count) || [0]))
);
const loginMax = computed(() =>
  Math.max(1, ...(store.metrics?.logins_last_7_days.map((p) => p.count) || [0]))
);
const distMax = computed(() =>
  Math.max(1, ...(store.metrics?.role_distribution.map((r) => r.count) || [0]))
);

const hasData = (points: { count: number }[]) => (points || []).some((p) => p.count > 0);
const barHeight = (count: number, max: number) => Math.max(4, Math.round((count / max) * 100));
const distWidth = (count: number) => Math.round((count / distMax.value) * 100);
const shortDate = (iso: string) => iso.slice(5);
const roleLabel = (role: string) => ROLE_LABELS[role as UserRole] || role;

onMounted(() => {
  if (!store.metrics) store.fetchMetrics();
});
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.section-title h3 {
  color: var(--primary-color);
  font-size: 1.2rem;
}
.btn-refresh {
  border: 1px solid var(--border-color, #e3eaf3);
  background: var(--white);
  color: var(--primary-color);
  padding: 8px 14px;
  border-radius: 14px;
  cursor: pointer;
  font-weight: 600;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.08);
}
.btn-refresh:disabled {
  opacity: 0.6;
  cursor: default;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(150px, 100%), 1fr));
  gap: 14px;
}
.stat-card {
  background: var(--white);
  border: 1px solid var(--border-color, #e3eaf3);
  border-radius: var(--border-radius);
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: var(--shadow);
}
.stat-icon {
  font-size: 1.8rem;
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-color);
  border-radius: 50%;
}
.stat-value {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-color);
}
.stat-label {
  font-size: 0.85rem;
  color: var(--text-light);
}
.charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(280px, 100%), 1fr));
  gap: 14px;
}
.chart-card {
  background: var(--white);
  border: 1px solid var(--border-color, #e3eaf3);
  border-radius: var(--border-radius);
  padding: 18px;
  box-shadow: var(--shadow);
}
.chart-card h4 {
  color: var(--text-color);
  margin-bottom: 14px;
  font-size: 1rem;
}
.bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: clamp(120px, 22vw, 160px);
  gap: 8px;
}
.bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  justify-content: flex-end;
}
.bar {
  width: 70%;
  background: linear-gradient(var(--primary-light), var(--primary-color));
  border-radius: 8px 8px 0 0;
  position: relative;
  min-height: 4px;
  transition: height 0.4s ease;
}
.bar-alt {
  background: linear-gradient(#a7d3f0, #6fa8dc);
}
.bar-num {
  position: absolute;
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.75rem;
  color: var(--text-light);
}
.bar-label {
  margin-top: 6px;
  font-size: 0.7rem;
  color: var(--text-light);
}
.dist {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.dist-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.dist-label {
  flex: 0 0 auto;
  width: 90px;
  font-size: 0.85rem;
  color: var(--text-color);
}
.dist-track {
  flex: 1;
  height: 14px;
  background: var(--bg-color);
  border-radius: 8px;
  overflow: hidden;
}
.dist-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-light), var(--primary-color));
  border-radius: 8px;
  transition: width 0.4s ease;
}
.dist-count {
  width: 40px;
  text-align: right;
  font-weight: 700;
  color: var(--text-color);
}
.empty-mini,
.empty-box,
.loading-box {
  text-align: center;
  color: var(--text-light);
  padding: 30px;
}
.empty-mini i,
.empty-box i {
  font-size: 2rem;
  margin-bottom: 10px;
  display: block;
}

@media (max-width: 640px) {
  .stat-card {
    padding: 12px;
    gap: 10px;
  }
  .stat-icon {
    width: 42px;
    height: 42px;
    font-size: 1.4rem;
  }
  .stat-value {
    font-size: 1.3rem;
  }
  .chart-card {
    padding: 14px;
  }
  .chart-card h4 {
    font-size: 0.92rem;
  }
  .bars {
    gap: 4px;
  }
  .bar-num {
    top: -16px;
    font-size: 0.65rem;
  }
  .bar-label {
    margin-top: 4px;
    font-size: 0.62rem;
  }
  .dist-row {
    gap: 8px;
  }
  .dist-label {
    width: 58px;
    font-size: 0.75rem;
  }
  .dist-count {
    width: 26px;
    font-size: 0.8rem;
  }
}
</style>
