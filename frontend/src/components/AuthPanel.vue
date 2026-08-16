<template>
  <section class="auth-shell">
    <div class="auth-intro">
      <div class="auth-orbit" aria-hidden="true">
        <span class="orbit-ring orbit-ring-one"></span>
        <span class="orbit-ring orbit-ring-two"></span>
        <span class="orbit-core"
          ><i class="fas fa-wand-magic-sparkles"></i
        ></span>
      </div>
      <div class="auth-intro-copy">
        <span class="auth-eyebrow">NOVA INTELLIGENCE</span>
        <h1>让知识连接，<br />让答案发生。</h1>
        <p>融合智能检索、可信引用与多轮对话，为你的每一次探索提供清晰答案。</p>
        <div class="auth-capabilities">
          <span><i class="fas fa-bolt"></i> 智能检索</span>
          <span><i class="fas fa-link"></i> 溯源引用</span>
          <span><i class="fas fa-layer-group"></i> 知识管理</span>
        </div>
        <a
          class="auth-github-link"
          href="https://github.com/amd47802574/NovaChat"
          target="_blank"
          rel="noopener noreferrer"
          title="GitHub 仓库"
        >
          <i class="fab fa-github"></i>
          <span>在 GitHub 上查看项目</span>
        </a>
      </div>
    </div>

    <div class="auth-panel">
      <div class="auth-panel-heading">
        <span class="auth-panel-kicker">{{
          authStore.authMode === 'login' ? 'WELCOME BACK' : 'CREATE ACCOUNT'
        }}</span>
        <h2>
          {{ authStore.authMode === 'login' ? '登录星智问答' : '注册星智问答' }}
        </h2>
        <p>
          {{
            authStore.authMode === 'login'
              ? '继续进入你的智能知识工作区'
              : '创建账号，开启智能问答体验'
          }}
        </p>
      </div>
      <div class="auth-form">
        <label class="auth-field">
          <span>用户名</span>
          <div class="auth-input-wrap">
            <i class="fas fa-user"></i>
            <input
              v-model="authStore.authForm.username"
              type="text"
              placeholder="请输入用户名"
              @keyup.enter="onSubmit"
            />
          </div>
        </label>
        <label class="auth-field">
          <span>密码</span>
          <div class="auth-input-wrap">
            <i class="fas fa-lock"></i>
            <input
              v-model="authStore.authForm.password"
              type="password"
              placeholder="请输入密码"
              @keyup.enter="onSubmit"
            />
          </div>
        </label>

        <label v-if="authStore.authMode === 'register'" class="auth-field">
          <span>账号类型</span>
          <div class="auth-input-wrap">
            <i class="fas fa-id-badge"></i>
            <select v-model="authStore.authForm.role">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>
        </label>

        <label
          v-if="
            authStore.authMode === 'register' &&
            authStore.authForm.role === 'admin'
          "
          class="auth-field"
        >
          <span>管理员邀请码</span>
          <div class="auth-input-wrap">
            <i class="fas fa-key"></i>
            <input
              v-model="authStore.authForm.admin_code"
              type="password"
              placeholder="请输入管理员邀请码"
              @keyup.enter="onSubmit"
            />
          </div>
        </label>

        <button
          class="send-btn auth-submit"
          :disabled="authStore.authLoading"
          @click="onSubmit"
        >
          <span>{{
            authStore.authLoading
              ? '提交中...'
              : authStore.authMode === 'login'
                ? '进入工作区'
                : '创建账号'
          }}</span>
          <i class="fas fa-arrow-right"></i>
        </button>

        <button class="auth-switch" @click="toggleAuthMode">
          {{
            authStore.authMode === 'login'
              ? '还没有账号？立即注册'
              : '已有账号？返回登录'
          }}
        </button>
      </div>
      <div class="auth-footer">
        <a
          class="icp-link"
          href="https://beian.miit.gov.cn/"
          target="_blank"
          rel="noopener noreferrer"
          >赣ICP备2026017220号</a
        >
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { useAuthStore } from '@/stores/auth'
  import { useChatStore } from '@/stores/chat'
  import { useSessionStore } from '@/stores/sessions'

  const authStore = useAuthStore()
  const chatStore = useChatStore()
  const sessionStore = useSessionStore()

  const toggleAuthMode = () => {
    authStore.authMode = authStore.authMode === 'login' ? 'register' : 'login'
  }

  const onSubmit = async () => {
    try {
      await authStore.handleAuthSubmit()
      try {
        await sessionStore.fetchSessions()
        chatStore.mergeCachedSessionsIntoHistory()
      } catch (_) {
        // 历史列表加载失败不影响恢复当前会话内容。
      }
      await chatStore.restoreLastSession()
    } catch (error: any) {
      alert(error.message)
    }
  }
</script>
