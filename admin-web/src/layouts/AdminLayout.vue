<template>
  <div class="shell" :class="{ collapsed, drawer: mobileOpen }">
    <!-- 侧栏 -->
    <aside class="aside" @click.self="mobileOpen = false">
      <div class="brand">
        <div class="brand-mark">知</div>
        <div class="brand-text" v-show="!collapsed">
          <b>知行岛后台</b>
          <span>v {{ version }}</span>
        </div>
      </div>

      <div class="aside-scroll">
        <el-menu
          :default-active="route.path"
          :collapse="collapsed"
          :collapse-transition="false"
          router
          class="nav"
        >
          <template v-for="item in menu" :key="item.title">
            <el-menu-item v-if="!item.children" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title><span>{{ item.title }}</span></template>
            </el-menu-item>
            <el-sub-menu v-else :index="item.title">
              <template #title>
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.title }}</span>
              </template>
              <el-menu-item v-for="c in item.children" :key="c.path" :index="c.path">
                <span class="sub-dot"></span>{{ c.title }}
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-menu>
      </div>

      <button class="collapse-btn" @click="collapsed = !collapsed" :title="collapsed ? '展开' : '收起'">
        <el-icon><component :is="collapsed ? Expand : Fold" /></el-icon>
      </button>
    </aside>

    <!-- 主内容 -->
    <div class="main">
      <header class="topbar">
        <div class="tl">
          <button class="icon-btn mobile-only" @click="mobileOpen = !mobileOpen"><el-icon><Menu /></el-icon></button>
          <div class="crumb">
            <span class="c-group">{{ crumb.group }}</span>
            <el-icon class="c-sep"><ArrowRight /></el-icon>
            <b class="c-page">{{ crumb.page }}</b>
          </div>
        </div>
        <div class="tr">
          <button class="search-btn" @click="openSearch">
            <el-icon><Search /></el-icon>
            <span>搜索页面 / 用户 / 订单</span>
            <kbd>{{ macLike ? '⌘' : 'Ctrl' }} K</kbd>
          </button>
          <el-popover placement="bottom-end" width="320" trigger="click">
            <template #reference>
              <button class="icon-btn notify"><el-icon><Bell /></el-icon><span v-if="notifyCount" class="notify-dot">{{ notifyCount }}</span></button>
            </template>
            <div class="notify-panel">
              <div class="np-head"><b>通知</b><a @click="clearNotify">全部标记已读</a></div>
              <div v-if="notifications.length" class="np-list">
                <a v-for="n in notifications" :key="n.id" class="np-item" @click="onNotify(n)">
                  <span class="np-icon" :class="n.kind"><el-icon><component :is="n.icon" /></el-icon></span>
                  <div><b>{{ n.title }}</b><i>{{ n.time }}</i></div>
                </a>
              </div>
              <div v-else class="np-empty">暂无未读通知</div>
            </div>
          </el-popover>
          <el-dropdown trigger="click" @command="onUserAction">
            <div class="user-chip">
              <span class="avatar">A</span>
              <span class="uname">管理员</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile"><el-icon><User /></el-icon>账号信息</el-dropdown-item>
                <el-dropdown-item command="password"><el-icon><Key /></el-icon>修改密码</el-dropdown-item>
                <el-dropdown-item command="landing"><el-icon><HomeFilled /></el-icon>产品官网</el-dropdown-item>
                <el-dropdown-item divided command="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <main class="content"><router-view /></main>
    </div>

    <!-- 搜索命令面板（占位实现） -->
    <el-dialog v-model="searchOpen" width="min(560px, 92vw)" :show-close="false" class="cmdk-dialog">
      <template #header>
        <div class="cmdk-input">
          <el-icon><Search /></el-icon>
          <input v-model="searchQuery" placeholder="搜索页面、订单、用户..." autofocus />
          <kbd>ESC</kbd>
        </div>
      </template>
      <div class="cmdk-list">
        <div class="cmdk-group">页面</div>
        <a v-for="r in filteredPages" :key="r.path" class="cmdk-row" @click="gotoRoute(r.path)">
          <el-icon><component :is="r.icon || Grid" /></el-icon>
          <div><b>{{ r.title }}</b><i>{{ r.group }}</i></div>
          <el-icon class="row-chev"><ArrowRight /></el-icon>
        </a>
        <div v-if="!filteredPages.length" class="cmdk-empty">未找到匹配项</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowDown, ArrowRight, Bell, Calendar, Cpu, Fold, Expand, Grid, HomeFilled, Key,
  Menu, Monitor, Reading, Search, Setting, ShoppingBag, SwitchButton,
  Ticket, TrendCharts, User, Wallet, Warning,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const collapsed = ref(false)
const mobileOpen = ref(false)
const searchOpen = ref(false)
const searchQuery = ref('')
const version = '2.0'
const macLike = /Mac|iPhone|iPad/.test(navigator.platform)

// ============ 菜单（top-level icon + subs） ============
const menu = shallowRef([
  { title: '数据总览', path: '/dashboard', icon: TrendCharts },
  { title: '收款管理', path: '/receipts', icon: Wallet },
  { title: '实时占座', path: '/live-board', icon: Monitor },
  {
    title: '首页 · 运营', icon: HomeFilled,
    children: [
      { title: '首页活动', path: '/banners' },
      { title: '消息公告', path: '/announcements' },
      { title: '站内消息', path: '/notifications' },
      { title: '联系店长', path: '/contact-setting' },
      { title: '门店管理', path: '/stores' },
      { title: '营业日历', path: '/store-calendar' },
    ],
  },
  {
    title: '订座 · 入座', icon: Calendar,
    children: [
      { title: '价格管理', path: '/pricing' },
      { title: '预约规则', path: '/booking-setting' },
      { title: '座位管理', path: '/seats' },
      { title: '预约订单', path: '/reservations' },
      { title: '蓝牙锁管理', path: '/locks' },
      { title: '开门记录', path: '/door-logs' },
    ],
  },
  {
    title: '套餐 · 卡券', icon: Ticket,
    children: [
      { title: '套餐购买', path: '/card-purchase-orders' },
      { title: '期限卡', path: '/period-cards' },
      { title: '团购映射', path: '/deal-mappings' },
      { title: '兑换记录', path: '/exchange-records' },
      { title: '优惠券', path: '/coupons' },
    ],
  },
  {
    title: '用户 · 资产', icon: User,
    children: [
      { title: '用户管理', path: '/users' },
      { title: '钱包流水', path: '/wallet-logs' },
      { title: '积分流水', path: '/point-logs' },
      { title: '邀请记录', path: '/invites' },
    ],
  },
  {
    title: '学习助手', icon: Reading,
    children: [
      { title: '学习数据', path: '/study-data' },
      { title: 'AI 使用统计', path: '/assistant-usage' },
      { title: 'AI 知识库', path: '/knowledge' },
      { title: '错题本', path: '/wrongbook' },
    ],
  },
  {
    title: '上岸集市', icon: ShoppingBag,
    children: [
      { title: '内容审核', path: '/market-listings' },
      { title: '举报·分类·限制', path: '/market-ops' },
    ],
  },
  {
    title: '系统', icon: Setting,
    children: [
      { title: '系统状态', path: '/system-status' },
      { title: '操作日志', path: '/operation-logs' },
      { title: '管理员', path: '/admins' },
    ],
  },
])

// ============ 面包屑 ============
const pathIndex = computed(() => {
  const idx = new Map<string, { group: string; page: string; icon?: any }>()
  for (const m of menu.value) {
    if (m.path) idx.set(m.path, { group: '总览', page: m.title, icon: m.icon })
    for (const c of m.children || []) idx.set(c.path, { group: m.title, page: c.title, icon: m.icon })
  }
  return idx
})
const crumb = computed(() => pathIndex.value.get(route.path) || { group: '', page: '页面' })

// ============ 通知（模拟 UI） ============
const notifications = ref([
  { id: 1, title: '本月有 1 家门店座位未配置完整', time: '2 小时前', kind: 'warn', icon: Warning, link: '/seats' },
  { id: 2, title: '收款管理有 3 笔核销待核对', time: '今日 09:12', kind: 'info', icon: Ticket, link: '/receipts' },
])
const notifyCount = computed(() => notifications.value.length)
function clearNotify() { notifications.value = []; ElMessage.success('已全部标记已读') }
function onNotify(n: any) { router.push(n.link); notifications.value = notifications.value.filter(x => x.id !== n.id) }

// ============ 用户操作 ============
function onUserAction(cmd: string) {
  if (cmd === 'logout') { localStorage.removeItem('admin_token'); router.push('/login'); return }
  if (cmd === 'landing') { router.push('/landing'); return }
  if (cmd === 'profile' || cmd === 'password') ElMessage.info('功能开发中，请稍候')
}

// ============ 全局搜索（命令面板） ============
function openSearch() { searchOpen.value = true; searchQuery.value = '' }
const allPages = computed(() => {
  const out: any[] = []
  for (const m of menu.value) {
    if (m.path) out.push({ path: m.path, title: m.title, group: '总览', icon: m.icon })
    for (const c of m.children || []) out.push({ path: c.path, title: c.title, group: m.title, icon: m.icon })
  }
  return out
})
const filteredPages = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return allPages.value.slice(0, 8)
  return allPages.value.filter(p =>
    p.title.toLowerCase().includes(q) || p.group.toLowerCase().includes(q) || p.path.includes(q)
  ).slice(0, 12)
})
function gotoRoute(path: string) { router.push(path); searchOpen.value = false }

function onKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openSearch() }
  if (e.key === 'Escape' && searchOpen.value) searchOpen.value = false
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  height: 100vh;
  background: var(--surface-2);
  transition: grid-template-columns 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.shell.collapsed { grid-template-columns: 68px 1fr; }

/* ============ 侧栏 ============ */
.aside {
  position: relative;
  background: #14161a;
  color: #d0d1d6;
  display: flex; flex-direction: column;
  overflow: hidden;
  border-right: 1px solid rgba(255,255,255,0.05);
}

.brand {
  display: flex; align-items: center; gap: 12px;
  padding: 20px 18px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  flex-shrink: 0;
}
.brand-mark {
  width: 36px; height: 36px; border-radius: 10px;
  background: linear-gradient(135deg, #FFD000, #ffb400);
  color: #1a1a1a; font-weight: 700; font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 20px rgba(255, 208, 0, 0.35);
  flex-shrink: 0;
}
.brand-text b { display: block; font-size: 14px; color: #f5f5f7; font-weight: 600; letter-spacing: 0.5px; }
.brand-text span { display: block; font-size: 11px; color: #7a7b83; letter-spacing: 0.5px; margin-top: 2px; }

.aside-scroll { flex: 1; overflow-y: auto; padding: 12px 10px; }
.aside-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); }

/* Menu deep overrides */
:deep(.el-menu--collapse) { width: 48px; }
:deep(.nav.el-menu) { background: transparent; }
:deep(.nav .el-menu-item),
:deep(.nav .el-sub-menu__title) {
  color: #9a9ba3 !important;
  border-radius: 10px;
  margin-bottom: 2px;
  height: 40px !important;
  line-height: 40px !important;
  font-size: 13.5px;
  transition: background 0.2s, color 0.2s;
}
:deep(.nav .el-menu-item:hover),
:deep(.nav .el-sub-menu__title:hover) {
  background: rgba(255,255,255,0.04) !important;
  color: #f5f5f7 !important;
}
:deep(.nav .el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(255, 208, 0, 0.12), rgba(255, 208, 0, 0.02)) !important;
  color: #FFD000 !important;
  font-weight: 500;
  box-shadow: inset 3px 0 0 #FFD000;
}
:deep(.nav .el-sub-menu.is-active .el-sub-menu__title) { color: #f5f5f7 !important; }
:deep(.nav .el-sub-menu .el-menu-item) { padding-left: 44px !important; height: 34px !important; line-height: 34px !important; font-size: 13px; }
:deep(.nav .el-icon) { color: inherit !important; }
:deep(.nav .el-menu-item.is-active .el-icon) { color: #FFD000 !important; }
.sub-dot {
  display: inline-block; width: 5px; height: 5px; border-radius: 50%;
  background: currentColor; opacity: 0.35; margin-right: 10px;
}
:deep(.nav .el-menu-item.is-active .sub-dot) { opacity: 1; }

.collapse-btn {
  border: 0; margin: 0;
  background: rgba(255,255,255,0.04);
  color: #9a9ba3;
  padding: 12px 0;
  cursor: pointer;
  border-top: 1px solid rgba(255,255,255,0.05);
  transition: background 0.2s, color 0.2s;
  font-size: 14px;
}
.collapse-btn:hover { background: rgba(255, 208, 0, 0.08); color: #FFD000; }

/* ============ 主内容 ============ */
.main { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }

.topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 24px; height: 60px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}
.tl, .tr { display: flex; align-items: center; gap: 12px; }

.crumb { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.c-group { color: var(--muted); font-weight: 500; }
.c-sep { font-size: 10px; color: #c0c1c9; }
.c-page { color: var(--ink); font-weight: 600; font-size: 14px; }

.icon-btn {
  background: transparent; border: 0; padding: 8px;
  width: 36px; height: 36px; border-radius: 10px;
  color: var(--ink-3); cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  position: relative;
  transition: background 0.2s;
}
.icon-btn:hover { background: var(--surface-3); color: var(--ink); }
.mobile-only { display: none; }

.notify-dot {
  position: absolute; top: 5px; right: 5px;
  min-width: 16px; height: 16px; padding: 0 4px;
  border-radius: 999px;
  background: #ef4444; color: #fff;
  font-size: 10px; font-weight: 600;
  display: inline-flex; align-items: center; justify-content: center;
  border: 2px solid #fff;
}

.search-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-radius: 10px;
  background: var(--surface-3); border: 1px solid var(--line);
  color: var(--muted); font-size: 13px; cursor: pointer;
  min-width: 240px;
  transition: background 0.2s, border-color 0.2s;
}
.search-btn:hover { background: #fff; border-color: var(--line-2); color: var(--ink-3); }
.search-btn span { flex: 1; text-align: left; }
.search-btn kbd, .cmdk-input kbd {
  padding: 2px 6px; font-size: 11px; font-family: inherit;
  background: #fff; border: 1px solid var(--line); border-radius: 6px;
  color: var(--muted); letter-spacing: 0.3px;
  box-shadow: 0 1px 0 var(--line);
}

.user-chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 10px 6px 6px; border-radius: 999px;
  background: var(--surface-3); border: 1px solid var(--line);
  cursor: pointer; transition: border-color 0.2s;
}
.user-chip:hover { border-color: var(--line-2); }
.avatar {
  width: 26px; height: 26px; border-radius: 50%;
  background: linear-gradient(135deg, #FFD000, #ffb400);
  color: var(--brand-fg); font-weight: 700; font-size: 12px;
  display: inline-flex; align-items: center; justify-content: center;
}
.uname { font-size: 13px; color: var(--ink); font-weight: 500; }

/* ============ 通知面板 ============ */
.notify-panel { padding: 4px; }
.np-head { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px 12px; border-bottom: 1px solid var(--line); }
.np-head b { color: var(--ink); font-size: 14px; }
.np-head a { color: var(--muted); font-size: 12px; cursor: pointer; }
.np-head a:hover { color: var(--brand-hover); }
.np-list { padding: 6px 0; max-height: 320px; overflow: auto; }
.np-item {
  display: flex; gap: 10px; padding: 10px 12px; border-radius: 8px; cursor: pointer;
  transition: background 0.2s;
}
.np-item:hover { background: var(--surface-3); }
.np-icon {
  width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center; font-size: 15px;
}
.np-icon.warn { background: rgba(240, 165, 0, 0.15); color: var(--warn); }
.np-icon.info { background: rgba(99, 102, 241, 0.15); color: #6366f1; }
.np-item b { display: block; font-size: 13px; color: var(--ink); font-weight: 500; margin-bottom: 2px; }
.np-item i { font-style: normal; font-size: 11.5px; color: var(--muted); }
.np-empty { padding: 32px 16px; text-align: center; color: var(--muted); font-size: 13px; }

/* ============ 命令面板 ============ */
:global(.cmdk-dialog .el-dialog__header) { padding: 0 !important; border: none !important; }
:global(.cmdk-dialog .el-dialog__body) { padding: 0 !important; }
.cmdk-input {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 20px; border-bottom: 1px solid var(--line);
}
.cmdk-input input {
  flex: 1; border: 0; outline: 0; background: transparent;
  font-size: 15px; color: var(--ink); font-family: inherit;
}
.cmdk-input input::placeholder { color: var(--muted); }
.cmdk-list { padding: 8px; max-height: 60vh; overflow: auto; }
.cmdk-group { padding: 8px 12px 4px; font-size: 11px; color: var(--muted); letter-spacing: 0.5px; text-transform: uppercase; font-weight: 600; }
.cmdk-row {
  display: flex; gap: 12px; align-items: center;
  padding: 10px 12px; border-radius: 10px; cursor: pointer;
  transition: background 0.15s;
}
.cmdk-row:hover { background: var(--surface-3); }
.cmdk-row > .el-icon:first-child {
  width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  background: var(--surface-3); color: var(--ink-3);
  display: inline-flex; align-items: center; justify-content: center; font-size: 15px;
}
.cmdk-row div { flex: 1; }
.cmdk-row b { display: block; font-size: 14px; color: var(--ink); font-weight: 500; }
.cmdk-row i { font-style: normal; font-size: 12px; color: var(--muted); }
.cmdk-row .row-chev { color: var(--muted); font-size: 12px; }
.cmdk-empty { padding: 32px 16px; text-align: center; color: var(--muted); font-size: 13px; }

/* ============ 内容区 ============ */
.content { flex: 1; min-height: 0; overflow: auto; padding: 20px 24px; }

/* ============ 响应式 ============ */
@media (max-width: 768px) {
  .shell { grid-template-columns: 1fr !important; }
  .aside {
    position: fixed; top: 0; left: 0; bottom: 0; width: 260px; z-index: 1000;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
  }
  .shell.drawer .aside { transform: translateX(0); box-shadow: 20px 0 60px rgba(0,0,0,0.3); }
  .shell.drawer::after {
    content: ''; position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 999;
    animation: fade-in 0.2s ease;
  }
  @keyframes fade-in { from { opacity: 0 } to { opacity: 1 } }
  .mobile-only { display: inline-flex; }
  .search-btn { min-width: 0; padding: 8px; }
  .search-btn span, .search-btn kbd { display: none; }
  .uname { display: none; }
  .content { padding: 16px; }
}
</style>
