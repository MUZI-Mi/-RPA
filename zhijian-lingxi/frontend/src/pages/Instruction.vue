<template>
  <div class="chat-page">
    <!-- 对话区 -->
    <div class="chat-area" ref="chatAreaRef">
      <!-- 空状态：居中大标题（豆包风格） -->
      <div v-if="!config && !nlText" class="welcome">
        <div class="welcome-avatar">
          <el-icon><MagicStick /></el-icon>
        </div>
        <h1 class="welcome-title">你好，我是智简灵析</h1>
        <p class="welcome-sub">用一句话描述需求，我来帮你自动完成网页操作</p>
      </div>

      <!-- 用户消息气泡 -->
      <div v-if="userMessage" class="msg-row user-row">
        <div class="bubble user-bubble">{{ userMessage }}</div>
      </div>

      <!-- AI 解析结果气泡 -->
      <div v-if="config" class="msg-row ai-row">
        <div class="ai-avatar">
          <el-icon><MagicStick /></el-icon>
        </div>
        <div class="bubble ai-bubble">
          <div class="ai-bubble-head">
            <span class="ai-name">已为你生成自动化方案</span>
            <el-tag size="small" type="success" effect="light">解析成功</el-tag>
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
              <el-button size="small" round @click="addStep">
                <el-icon><Plus /></el-icon>添加步骤
              </el-button>
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
      <!-- 建议卡片 -->
      <div v-if="!config" class="suggestions">
        <div
          v-for="s in suggestions"
          :key="s.text"
          class="suggestion-card"
          @click="applySuggestion(s.text)"
        >
          <el-icon class="sug-icon"><component :is="s.icon" /></el-icon>
          <div class="sug-text">
            <div class="sug-title">{{ s.title }}</div>
            <div class="sug-desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>

      <div class="input-box">
        <el-input
          v-model="nlText"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="描述你想让 AI 自动完成的事情，例如：每天早上9点打开钉钉签到"
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
      <div class="input-tip">Ctrl + Enter 快速发送 · 解析结果需确认后才会执行</div>
    </div>

    <RuleEditor v-model="editorVisible" :step="editingStep" :steps="config?.steps" @save="saveStep" />
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
import { useTaskStore } from "@/stores/task";

const router = useRouter();
const route = useRoute();
const taskStore = useTaskStore();
const editTaskId = ref<string | null>(null);

const nlText = ref("");
const userMessage = ref("");
const parsing = ref(false);
const saving = ref(false);
const recording = ref(false);
const chatAreaRef = ref<HTMLElement>();

const config = ref<TaskConfig | null>(null);
const editorVisible = ref(false);
const editingIndex = ref(-1);
const editingStep = ref<Step | null>(null);

const suggestions = [
  { icon: "AlarmClock", title: "定时签到", desc: "每天早上9点打开钉钉签到", text: "每天早上9点打开钉钉签到" },
  { icon: "Search", title: "信息采集", desc: "打开百度搜索大创项目并保存结果", text: "打开百度搜索大创项目，把第一条结果标题保存下来" },
  { icon: "Document", title: "表单填写", desc: "把表格数据自动填到系统里", text: "打开OA系统，把本周工作周报填写到周报表单里" },
  { icon: "Download", title: "文件下载", desc: "定时下载最新报表", text: "每周一早上8点打开财务系统下载最新月度报表" },
];

const defaultConfig: TaskConfig = {
  task_name: "新任务",
  description: "",
  schedule: { type: "once" },
  speed_mode: "normal",
  steps: [],
};

function applySuggestion(text: string) {
  nlText.value = text;
  handleParse();
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
  userMessage.value = nlText.value.trim();
  parsing.value = true;
  scrollToBottom();
  try {
    const res = await api.parseNL(userMessage.value);
    config.value = res.config;
    ElMessage.success("解析成功，请确认后运行");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "解析失败");
    userMessage.value = "";
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
  userMessage.value = "";
  nlText.value = "";
}

function addStep() {
  const cfg = config.value || JSON.parse(JSON.stringify(defaultConfig));
  config.value = cfg;
  const step: Step = { step_id: cfg.steps.length + 1, condition: { type: "always" }, action: { type: "click" } };
  cfg.steps.push(step);
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
      await api.startRecording(value.trim());
      recording.value = true;
      ElMessage.info("录制中，请在打开的浏览器窗口操作");
    } catch (e: any) {
      // 用户取消弹框时 ElMessageBox 会 reject，忽略即可
      if (e === "cancel" || e === "close") return;
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
  max-width: 860px;
  margin: 0 auto;
  padding: 0 24px;
}

/* ===== 对话区 ===== */
.chat-area {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding-top: 40px;
}

/* 欢迎区（豆包居中大标题） */
.welcome {
  margin: auto;
  text-align: center;
  padding-bottom: 40px;
}
.welcome-avatar {
  width: 64px;
  height: 64px;
  margin: 0 auto 20px;
  border-radius: 20px;
  background: linear-gradient(135deg, #2e6ef5, #7aa5f9);
  color: #fff;
  font-size: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(46, 110, 245, 0.35);
}
.welcome-title {
  font-size: 30px;
  font-weight: 600;
  color: var(--db-text);
  margin: 0 0 10px;
}
.welcome-sub {
  font-size: 15px;
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
  max-width: 78%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
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
  max-width: none;
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
  padding: 12px 0 20px;
}

.suggestions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}
.suggestion-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid var(--db-border);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.suggestion-card:hover {
  border-color: var(--db-primary);
  box-shadow: var(--db-shadow-hover);
  transform: translateY(-1px);
}
.sug-icon {
  font-size: 20px;
  color: var(--db-primary);
  background: var(--db-primary-light);
  border-radius: 8px;
  padding: 6px;
}
.sug-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--db-text);
}
.sug-desc {
  font-size: 12px;
  color: var(--db-text-muted);
  margin-top: 2px;
}

.input-box {
  background: #fff;
  border: 1px solid var(--db-border);
  border-radius: 16px;
  padding: 12px 14px 8px;
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
