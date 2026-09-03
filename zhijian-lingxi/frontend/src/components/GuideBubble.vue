<template>
  <div class="guide-root">
    <!-- 右上角常驻气泡按钮 -->
    <button class="guide-fab" :class="{ active: visible }" @click="visible = !visible" title="查看使用指引">
      <el-icon><QuestionFilled /></el-icon>
    </button>

    <!-- 详情卡（一次只显示一个步骤，左右翻页，右上角关闭） -->
    <transition name="guide-pop">
      <div v-if="visible" class="guide-card">
        <!-- 右上角关闭小气泡 -->
        <button class="guide-bubble guide-close" @click="close" title="关闭">
          <el-icon><Close /></el-icon>
        </button>

        <!-- 左/右翻页气泡 -->
        <button v-if="current > 0" class="guide-bubble guide-nav guide-prev" @click="prev" title="上一步">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <button
          v-if="current < steps.length - 1"
          class="guide-bubble guide-nav guide-next"
          @click="next"
          title="下一步"
        >
          <el-icon><ArrowRight /></el-icon>
        </button>

        <div class="guide-scroll">
          <div class="guide-head">
            <span class="guide-badge">{{ steps[current].badge }}</span>
            <span class="guide-title">{{ steps[current].title }}</span>
            <span class="guide-count">{{ current + 1 }} / {{ steps.length }}</span>
          </div>

          <p class="guide-desc" v-html="steps[current].desc"></p>
          <ol class="guide-list">
            <li v-for="(t, i) in steps[current].items" :key="i" v-html="t"></li>
          </ol>

          <el-button
            v-if="steps[current].button"
            type="primary"
            round
            size="large"
            class="guide-btn"
            :loading="steps[current].id === 'browser' && browserAttaching"
            @click="steps[current].action"
          >
            <el-icon v-if="steps[current].id !== 'browser' || !browserAttaching">
              <component :is="steps[current].icon" />
            </el-icon>
            {{ steps[current].button }}
            <el-icon class="guide-btn-arrow"><ArrowRight /></el-icon>
          </el-button>
          <p v-if="steps[current].note" class="guide-note">{{ steps[current].note }}</p>

          <!-- 步骤小圆点指示器 -->
          <div class="guide-dots">
            <span
              v-for="(_, i) in steps"
              :key="i"
              class="guide-dot"
              :class="{ active: i === current }"
              @click="current = i"
            />
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import * as api from "@/api";

const router = useRouter();
const visible = ref(false);
const current = ref(0);
const browserAttaching = ref(false);

// 首次访问自动弹出（关闭后不再自动弹）
const GUIDE_KEY = "zhlx_guide_first_visit";

interface GuideStep {
  id: string;
  badge: string;
  title: string;
  desc: string;
  items: string[];
  button?: string;
  icon?: string;
  note?: string;
  action?: () => void;
}

const steps: GuideStep[] = [
  {
    id: "llm",
    badge: "第一步 · 必做",
    title: "先配置大模型",
    desc: "我靠大模型听懂你的话、把需求变成操作步骤。请先到<b>设置</b>页填一下模型来源和 API Key（只需做一次）：",
    items: [
      "点击下方按钮，进入「设置」页；",
      "在「大模型配置」里选一个<b>模型来源</b>（如智谱 AI，有免费额度）；",
      "把该平台的 <b>API Key</b> 粘贴进去，点保存；",
      "配好后回来，就可以输入任务让我执行了。",
    ],
    button: "去设置页配置大模型",
    icon: "Setting",
    action: () => {
      router.push("/settings");
      close();
    },
  },
  {
    id: "browser",
    badge: "第二步 · 必做",
    title: "先接通你的浏览器",
    desc: "我需要在<b>你的浏览器</b>里操作，才能用上你已经登录的账号和数据。请按下面步骤先接通浏览器（只需做一次）：",
    items: [
      "点击下方按钮，系统会为你打开一个浏览器窗口；",
      "在这个新窗口里登录你要用的网站（如报销系统、政务平台）；",
      "做完这两步，就可以输入任务让我执行了。",
    ],
    button: "一键打开我的浏览器",
    icon: "Connection",
    note: "不接通浏览器时也能使用，但无法读取你的登录状态和数据，部分任务会受限。",
    action: handleLaunchBrowser,
  },
];

function close() {
  visible.value = false;
  localStorage.setItem(GUIDE_KEY, "1");
}

function next() {
  if (current.value < steps.length - 1) current.value += 1;
}

function prev() {
  if (current.value > 0) current.value -= 1;
}

// 一键打开调试浏览器（接管模式必须）：登录态/数据都在用户自己的浏览器里，
// 必须先以调试模式打开它，系统才能“接管”并读取你的登录数据完成任务。
async function handleLaunchBrowser() {
  if (browserAttaching.value) return;
  browserAttaching.value = true;
  try {
    const res = await api.launchBrowser();
    ElMessage.success(res.msg || "已启动浏览器窗口");
    ElMessageBox.alert(
      "已为你打开一个浏览器窗口。\n\n请在这个新窗口里登录你要操作的网站，登录一次后，以后都会保持登录状态，系统就能自动帮你完成任务了。",
      "请在新窗口完成登录",
      { confirmButtonText: "我知道了", type: "success" }
    );
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "浏览器启动失败");
  } finally {
    browserAttaching.value = false;
  }
}

onMounted(() => {
  if (!localStorage.getItem(GUIDE_KEY)) {
    setTimeout(() => {
      visible.value = true;
    }, 600);
  }
});
</script>

<style scoped>
.guide-root {
  /* 空容器：内部用 fixed 定位 */
}

/* 右上角常驻气泡 */
.guide-fab {
  position: fixed;
  top: 18px;
  right: 18px;
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, #2e6ef5, #6b9bf8);
  color: #fff;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(46, 110, 245, 0.4);
  transition: all 0.2s;
  z-index: 3000;
}
.guide-fab:hover {
  transform: scale(1.08);
}
.guide-fab.active {
  background: linear-gradient(135deg, #f56c6c, #f78f8f);
}

/* 详情卡 */
.guide-card {
  position: fixed;
  top: 72px;
  right: 18px;
  width: 344px;
  max-width: calc(100vw - 40px);
  background: #fff;
  border: 1px solid var(--db-border);
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(31, 35, 41, 0.16);
  padding: 20px 22px 14px;
  z-index: 3000;
  overflow: visible; /* 不裁剪左右探出的翻页气泡 */
}

/* 卡片内部滚动区：超高时这里滚，不影响外侧气泡 */
.guide-scroll {
  max-height: calc(100vh - 130px);
  overflow-y: auto;
}

/* 通用小气泡（关闭 + 翻页） */
.guide-bubble {
  position: absolute;
  width: 28px;
  height: 28px;
  border: 1px solid var(--db-border);
  border-radius: 50%;
  background: #fff;
  color: var(--db-text-secondary);
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(31, 35, 41, 0.12);
  transition: all 0.15s;
  z-index: 1;
}
.guide-bubble:hover {
  color: var(--db-primary);
  border-color: var(--db-primary);
}
.guide-close {
  top: -10px;
  right: -10px;
}
.guide-nav {
  top: 50%;
  margin-top: -14px;
}
.guide-prev {
  left: -13px;
}
.guide-next {
  right: -13px;
}

/* 卡片头部 */
.guide-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.guide-badge {
  background: #fff3e0;
  color: #e6a23c;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 20px;
  flex-shrink: 0;
}
.guide-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--db-text);
  flex: 1;
}
.guide-count {
  font-size: 12px;
  color: var(--db-text-muted);
  flex-shrink: 0;
}

.guide-desc {
  font-size: 13px;
  color: var(--db-text-secondary);
  line-height: 1.7;
  margin: 0 0 8px;
}
.guide-list {
  margin: 0 0 14px;
  padding-left: 20px;
}
.guide-list li {
  font-size: 13px;
  color: var(--db-text);
  line-height: 1.8;
}
.guide-btn {
  width: 100%;
  justify-content: center;
}
.guide-btn-arrow {
  margin-left: 4px;
}
.guide-note {
  font-size: 12px;
  color: var(--db-text-muted);
  line-height: 1.6;
  margin: 12px 0 0;
  text-align: center;
}

/* 步骤小圆点 */
.guide-dots {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-top: 12px;
}
.guide-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d9dde3;
  cursor: pointer;
  transition: all 0.15s;
}
.guide-dot.active {
  background: var(--db-primary);
  width: 18px;
  border-radius: 6px;
}

/* 弹出动画 */
.guide-pop-enter-active,
.guide-pop-leave-active {
  transition: all 0.2s ease;
  transform-origin: top right;
}
.guide-pop-enter-from,
.guide-pop-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.96);
}
</style>
