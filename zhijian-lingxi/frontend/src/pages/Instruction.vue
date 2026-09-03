<template>
  <div class="chat-page">
    <!-- 对话区 -->
    <div class="chat-area" ref="chatAreaRef">
      <!-- 空状态：居中大标题（豆包风格） -->
      <div v-if="!config && !userMessages.length && !nlText" class="welcome">
        <div class="welcome-avatar">
          <el-icon><MagicStick /></el-icon>
        </div>
        <h1 class="welcome-title">你好，我是智简灵析</h1>
        <p class="welcome-sub">用一句话描述需求，我来帮你自动完成网页操作</p>
      </div>

      <!-- 用户消息气泡（可多次发送，逐条展示） -->
      <div v-for="(m, i) in userMessages" :key="i" class="msg-row user-row">
        <div class="bubble user-bubble">{{ m }}</div>
      </div>

      <!-- AI 解析结果气泡 -->
      <div v-if="config" class="msg-row ai-row">
        <div class="ai-avatar">
          <el-icon><MagicStick /></el-icon>
        </div>
        <div class="bubble ai-bubble">
          <div class="ai-bubble-head">
            <span class="ai-name">{{ refinedCount ? "已按你的要求更新方案" : "已为你生成自动化方案" }}</span>
            <el-tag size="small" :type="refinedCount ? 'warning' : 'success'" effect="light">
              {{ refinedCount ? `已更新（第 ${refinedCount} 次）` : "解析成功" }}
            </el-tag>
          </div>

          <!-- 方案确认：AI 用大白话返回任务规则，供非技术用户确认 -->
          <div class="confirm-panel">
            <div class="confirm-title">
              <el-icon class="confirm-icon"><CircleCheckFilled /></el-icon>
              请确认这个方案
            </div>
            <p class="confirm-sub">我会按下面的顺序一步一步操作：</p>
            <ol class="confirm-list">
              <li v-for="s in config.steps" :key="s.step_id">{{ stepNote(s) }}</li>
            </ol>
            <p class="confirm-tip">
              确认无误后点下方「保存并运行」开始；还想调整，直接在下面再发一句告诉我就行，我会更新方案。
            </p>
          </div>

          <!-- 任务配置表单 -->
          <div class="config-panel">
            <div class="config-row">
              <span class="config-label">任务名称</span>
              <el-input v-model="config.task_name" size="default" class="config-input" />
            </div>
            <div class="config-row">
              <span class="config-label">调度方式</span>
              <div class="config-inline">
                <el-select v-model="config.schedule.type" style="width: 150px">
                  <el-option label="立即执行一次" value="once" />
                  <el-option label="Cron 定时" value="cron" />
                  <el-option label="固定间隔" value="interval" />
                  <el-option label="指定时间" value="date" />
                </el-select>
                <el-input
                  v-if="config.schedule.type === 'cron'"
                  v-model="config.schedule.expression"
                  placeholder="0 9 * * *"
                  style="width: 160px"
                />
                <el-input
                  v-if="config.schedule.type === 'date'"
                  v-model="config.schedule.run_date"
                  placeholder="2026-09-01 08:00"
                  style="width: 180px"
                />
              </div>
            </div>
            <div class="config-row">
              <span class="config-label">执行速度</span>
              <el-radio-group v-model="config.speed_mode">
                <el-radio-button value="fast">快速</el-radio-button>
                <el-radio-button value="normal">正常</el-radio-button>
                <el-radio-button value="slow">缓慢</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <!-- 步骤列表 -->
          <div class="steps-panel">
            <div class="steps-head">
              <span>执行步骤（{{ config.steps.length }}）</span>
              <el-space :size="8">
                <el-tooltip content="插入「打开第1个→关闭→第2个→…」的循环模板" placement="top">
                  <el-button size="small" round type="success" @click="insertLoop">
                    <el-icon><Refresh /></el-icon>插入循环
                  </el-button>
                </el-tooltip>
                <el-button size="small" round @click="addStep">
                  <el-icon><Plus /></el-icon>添加步骤
                </el-button>
              </el-space>
            </div>
            <draggable
              :list="config.steps"
              item-key="step_id"
              handle=".drag-handle"
              ghost-class="ghost"
            >
              <template #item="{ element, index }">
                <div class="step-item">
                  <el-icon class="drag-handle"><Rank /></el-icon>
                  <RuleCard
                    :step="element"
                    class="step-card"
                    @edit="editStep(index)"
                    @delete="removeStep(index)"
                  />
                </div>
              </template>
            </draggable>
            <el-empty v-if="!config.steps.length" description="暂无步骤" :image-size="60" />
          </div>

          <div class="bubble-actions">
            <el-button round @click="resetChat">重新输入</el-button>
            <el-button type="primary" round :loading="saving" @click="handleSave">
              <el-icon><VideoPlay /></el-icon>保存并运行
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部输入区（豆包式胶囊输入框） -->
    <div class="input-zone">
      <div class="input-box">
        <el-input
          v-model="nlText"
          type="textarea"
          :rows="1"
          :autosize="{ minRows: 1, maxRows: 6 }"
          resize="none"
          placeholder="描述你想让 AI 自动完成的事情，例如：打开哔哩哔哩点击热门第一个视频"
          @keydown.ctrl.enter="handleParse"
        />
        <div class="input-toolbar">
          <div class="toolbar-left">
            <el-tooltip content="录制浏览器操作自动生成规则" placement="top">
              <button class="tool-btn" :class="{ recording }" @click="handleRecord">
                <el-icon><VideoCamera /></el-icon>
                <span>{{ recording ? "停止录制" : "操作录制" }}</span>
              </button>
            </el-tooltip>
            <el-tooltip content="不用 AI，手动配置规则步骤" placement="top">
              <button class="tool-btn" @click="openManual">
                <el-icon><Edit /></el-icon>
                <span>手动配置</span>
              </button>
            </el-tooltip>
          </div>
          <button class="send-btn" :disabled="!nlText.trim() || parsing" @click="handleParse">
            <el-icon v-if="!parsing"><Promotion /></el-icon>
            <el-icon v-else class="is-loading"><Loading /></el-icon>
          </button>
        </div>
      </div>
      <div class="input-tip">Ctrl + Enter 快速发送 · 可多次发消息调整方案，确认无误后再执行</div>
    </div>

    <RuleEditor v-model="editorVisible" :step="editingStep" :steps="config?.steps" @save="saveStep" />

    <!-- 右上角使用指引气泡（首次访问自动弹出） -->
    <GuideBubble />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import draggable from "vuedraggable";
import { useRoute, useRouter } from "vue-router";
import type { Step, TaskConfig } from "@/types";
import * as api from "@/api";
import RuleCard from "@/components/RuleCard.vue";
import RuleEditor from "@/components/RuleEditor.vue";
import GuideBubble from "@/components/GuideBubble.vue";
import { useTaskStore } from "@/stores/task";

const router = useRouter();
const route = useRoute();
const taskStore = useTaskStore();
const editTaskId = ref<string | null>(null);

const nlText = ref("");
const userMessages = ref<string[]>([]);
const refinedCount = ref(0);
const parsing = ref(false);
const saving = ref(false);
const recording = ref(false);
const chatAreaRef = ref<HTMLElement>();

const config = ref<TaskConfig | null>(null);
const editorVisible = ref(false);
const editingIndex = ref(-1);
const editingStep = ref<Step | null>(null);

const defaultConfig: TaskConfig = {
  task_name: "新任务",
  description: "",
  schedule: { type: "once" },
  speed_mode: "normal",
  steps: [],
};

// 方案确认列表：优先用 AI 生成的大白话说明；个别步骤没生成时兜底用动作名+关键参数
function stepNote(s: Step): string {
  const n = s.note?.trim();
  if (n) return n;
  const a = s.action;
  const labels: Record<string, string> = {
    open: "打开网页", click: "点击", input: "输入", select: "选择", upload: "上传",
    scroll: "滚动", extract: "提取", wait: "等待", hover: "悬停", press_key: "按键",
    reload: "刷新当前网页", back: "后退一页", forward: "前进一页",
    close_tab: "关闭网页", foreach: "逐个打开并关闭列表中的内容", foreach_if: "逐条检查：命中的才处理，其余跳过", set_var: "设置变量",
    goto: "跳到指定步骤", if_text: "按文字判断", if_element: "按内容判断", if_var: "按结果判断",
    ocr: "OCR 读图（把图片变成文字）", llm_extract: "AI 抽取关键信息", export: "导出报表（数据文件）",
  };
  const base = labels[a.type] || a.type;
  const detail = a.url || a.text || a.value || a.selector || "";
  return detail ? `${base}：${detail}` : base;
}

function scrollToBottom() {
  nextTick(() => {
    chatAreaRef.value?.scrollTo({ top: chatAreaRef.value.scrollHeight, behavior: "smooth" });
  });
}

// 从任务列表点「编辑」进入：加载已有任务到编辑器
onMounted(async () => {
  const editId = route.query.edit as string | undefined;
  if (!editId) return;
  try {
    const task = await api.getTask(editId);
    editTaskId.value = task.id;
    config.value = task.config;
    ElMessage.info(`正在编辑任务「${task.name}」，修改后点保存生效`);
    scrollToBottom();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载任务失败");
  }
});

async function handleParse() {
  if (!nlText.value.trim() || parsing.value) return;
  const text = nlText.value.trim();
  userMessages.value.push(text);
  nlText.value = "";
  parsing.value = true;
  scrollToBottom();
  try {
    if (config.value) {
      // 已有方案 → 按用户新要求多轮修改
      const res = await api.refineNL(text, config.value);
      config.value = res.config;
      refinedCount.value += 1;
      ElMessage.success("已按你的要求更新方案，请再次确认");
    } else {
      const res = await api.parseNL(text);
      config.value = res.config;
      ElMessage.success("解析成功，请确认后运行");
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "处理失败");
    userMessages.value.pop();
  } finally {
    parsing.value = false;
    scrollToBottom();
  }
}

function openManual() {
  config.value = JSON.parse(JSON.stringify(defaultConfig));
  addStep();
  scrollToBottom();
}

function resetChat() {
  config.value = null;
  userMessages.value = [];
  refinedCount.value = 0;
  nlText.value = "";
}

function addStep() {
  const cfg = config.value || JSON.parse(JSON.stringify(defaultConfig));
  config.value = cfg;
  const step: Step = { step_id: cfg.steps.length + 1, condition: { type: "always" }, action: { type: "click" } };
  cfg.steps.push(step);
}

// 插入「打开第1个→关闭→第2个→…」的循环模板：
// set_var i=1 → click 第{{i}}个 → wait → close_tab → set_var i+1 → if_var i>N 结束否则跳回 click
function insertLoop() {
  const cfg = config.value || JSON.parse(JSON.stringify(defaultConfig));
  config.value = cfg;
  const start = cfg.steps.length;
  const clickStep = start + 2; // 循环体内「点击第{{i}}个」的 step_id
  const loopSteps: Step[] = [
    { step_id: start + 1, condition: { type: "always" }, action: { type: "set_var", var: "i", op: "set", value: "1" } },
    { step_id: start + 2, condition: { type: "always" }, action: { type: "click", selector: "请填写第 {{i}} 个目标的定位", text: "打开第 {{i}} 个目标" } },
    { step_id: start + 3, condition: { type: "always" }, action: { type: "wait", value: "2" } },
    { step_id: start + 4, condition: { type: "always" }, action: { type: "close_tab" } },
    { step_id: start + 5, condition: { type: "always" }, action: { type: "set_var", var: "i", op: "inc", value: "1" } },
    { step_id: start + 6, condition: { type: "always" }, action: { type: "if_var", var: "i", op: "greater", value: "3", goto_if_found: null, goto_if_not: clickStep } },
  ];
  cfg.steps.push(...loopSteps);
  ElMessage.info('已插入循环模板：点第{{i}}个 → 关闭 → 下一个。请修改第3步定位为实际内容，并把第8步循环次数改为所需值');
}

function editStep(index: number) {
  editingIndex.value = index;
  editingStep.value = config.value!.steps[index];
  editorVisible.value = true;
}

function saveStep(step: Step) {
  if (config.value && editingIndex.value >= 0) {
    config.value.steps[editingIndex.value] = step;
  }
}

function removeStep(index: number) {
  config.value?.steps.splice(index, 1);
  config.value?.steps.forEach((s, i) => (s.step_id = i + 1));
}

async function handleSave() {
  if (!config.value || !config.value.steps.length) {
    ElMessage.warning("请至少添加一个步骤");
    return;
  }
  saving.value = true;
  try {
    const name = config.value.task_name || "未命名任务";
    if (editTaskId.value) {
      await api.updateTask(editTaskId.value, { name, config: config.value });
      ElMessage.success("任务已更新");
    } else {
      await taskStore.addTask(name, config.value);
      ElMessage.success("任务已保存");
    }
    router.push("/tasks");
  } finally {
    saving.value = false;
  }
}

async function handleRecord() {
  if (!recording.value) {
    let startUrl = "";
    try {
      const { value } = await ElMessageBox.prompt(
        "请输入要录制操作的起始网址",
        "操作录制",
        {
          confirmButtonText: "开始录制",
          cancelButtonText: "取消",
          inputValue: "https://www.baidu.com",
          inputPlaceholder: "例如 https://login.dingtalk.com",
          inputPattern: /^https?:\/\/.+/,
          inputErrorMessage: "请输入以 http:// 或 https:// 开头的完整网址",
        }
      );
      startUrl = value.trim();
      await api.startRecording(startUrl);
      recording.value = true;
      ElMessage.info("录制中，请在打开的浏览器窗口操作");
    } catch (e: any) {
      // 用户取消弹框时 ElMessageBox 会 reject，忽略即可
      if (e === "cancel" || e === "close") return;
      // 上一次录制残留未结束（录制窗口被关/卡住）→ 强制清理后自动重试一次
      if (e?.response?.status === 409) {
        try {
          await api.forceStopRecording();
          await api.startRecording(startUrl);
          recording.value = true;
          ElMessage.info("已清理上次残留的录制，重新开始录制，请在打开的浏览器窗口操作");
          return;
        } catch (e2: any) {
          ElMessage.error(e2?.response?.data?.detail || "录制启动失败，仍被占用");
          return;
        }
      }
      ElMessage.error(e?.response?.data?.detail || "录制启动失败");
    }
  } else {
    try {
      const res = await api.stopRecording();
      recording.value = false;
      const cfg = JSON.parse(JSON.stringify(defaultConfig));
      cfg.task_name = "录制的任务";
      cfg.steps = res.steps;
      config.value = cfg;
      ElMessage.success("录制完成，已生成规则");
      scrollToBottom();
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || "录制停止失败");
    }
  }
}
</script>

<style scoped>
.chat-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 24px;
}

/* ===== 对话区 ===== */
.chat-area {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding-top: 16px;
}

/* 欢迎区（豆包居中大标题） */
.welcome {
  margin: auto;
  text-align: center;
  padding-bottom: 24px;
}
.welcome-avatar {
  width: 56px;
  height: 56px;
  margin: 0 auto 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, #2e6ef5, #7aa5f9);
  color: #fff;
  font-size: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(46, 110, 245, 0.35);
}
.welcome-title {
  font-size: 36px;
  font-weight: 700;
  color: var(--db-text);
  margin: 0 0 20px;
}
.welcome-sub {
  font-size: 16px;
  color: var(--db-text-secondary);
  margin: 0;
}

/* 消息气泡 */
.msg-row {
  display: flex;
  margin-bottom: 20px;
}
.user-row {
  justify-content: flex-end;
}
.bubble {
  max-width: 680px;
  padding: 16px 20px;
  border-radius: 16px;
  font-size: 16px;
  line-height: 24px;
}
.user-bubble {
  background: var(--db-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.ai-row {
  align-items: flex-start;
  gap: 10px;
}
.ai-avatar {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 12px;
  background: linear-gradient(135deg, #2e6ef5, #7aa5f9);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}
.ai-bubble {
  background: #fff;
  border: 1px solid var(--db-border);
  border-radius: 4px 16px 16px 16px;
  box-shadow: var(--db-shadow);
  flex: 1;
  max-width: 680px;
  font-size: 16px;
  line-height: 26px;
}
.ai-bubble-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.ai-name {
  font-weight: 600;
  font-size: 15px;
}

/* 方案确认面板（自然语言规则） */
.confirm-panel {
  background: #f0f9eb;
  border: 1px solid #d3ecbd;
  border-radius: 12px;
  padding: 14px 18px;
  margin-bottom: 14px;
}
.confirm-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #529b2e;
  margin-bottom: 6px;
}
.confirm-icon {
  font-size: 16px;
}
.confirm-sub {
  font-size: 13px;
  color: var(--db-text-secondary);
  margin: 0 0 6px;
}
.confirm-list {
  margin: 0;
  padding-left: 22px;
}
.confirm-list li {
  font-size: 16px;
  color: var(--db-text);
  line-height: 26px;
}
.confirm-tip {
  font-size: 12px;
  color: #8a8f99;
  line-height: 1.6;
  margin: 8px 0 0;
}

/* 配置面板 */
.config-panel {
  background: var(--db-primary-lighter);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 14px;
}
.config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0;
}
.config-label {
  width: 70px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--db-text-secondary);
}
.config-input {
  max-width: 320px;
}
.config-inline {
  display: flex;
  gap: 8px;
}

/* 步骤面板 */
.steps-panel {
  margin-bottom: 14px;
}
.steps-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
}
.step-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.drag-handle {
  cursor: move;
  color: #c0c4cc;
}
.drag-handle:hover {
  color: var(--db-primary);
}
.step-card {
  flex: 1;
}
.ghost {
  opacity: 0.5;
}

.bubble-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* ===== 底部输入区 ===== */
.input-zone {
  padding: 10px 0 16px;
}

.input-box {
  background: #fff;
  border: 1px solid var(--db-border);
  border-radius: 24px;
  padding: 12px 16px;
  transition: all 0.2s;
  box-shadow: 0 2px 12px rgba(31, 35, 41, 0.04);
}
.input-box:focus-within {
  border-color: var(--db-primary);
  box-shadow: 0 0 0 3px rgba(46, 110, 245, 0.12);
}
.input-box :deep(.el-textarea__inner) {
  box-shadow: none;
  padding: 4px 2px;
  font-size: 14px;
  background: transparent;
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 6px;
}
.toolbar-left {
  display: flex;
  gap: 6px;
}
.tool-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: none;
  border-radius: 20px;
  background: transparent;
  color: var(--db-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.tool-btn:hover {
  background: #f0f2f5;
  color: var(--db-text);
}
.tool-btn.recording {
  background: #ffeded;
  color: #f56c6c;
}

.send-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: var(--db-primary);
  color: #fff;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(46, 110, 245, 0.3);
}
.send-btn:hover:not(:disabled) {
  background: var(--db-primary-hover);
  transform: scale(1.05);
}
.send-btn:disabled {
  background: #c9cdd4;
  cursor: not-allowed;
  box-shadow: none;
}

.input-tip {
  text-align: center;
  font-size: 12px;
  color: var(--db-text-muted);
  margin-top: 10px;
}
</style>
