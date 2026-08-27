<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-head">
      <div>
        <h2 class="page-title">任务管理</h2>
        <p class="page-desc">管理你的自动化任务，随时执行、查看历史与报告</p>
      </div>
      <div class="head-actions">
        <el-button round @click="fetchTasks">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-upload :show-file-list="false" accept=".json" :before-upload="handleImport">
          <el-button round>
            <el-icon><Upload /></el-icon>导入
          </el-button>
        </el-upload>
        <el-button type="primary" round @click="$router.push('/')">
          <el-icon><Plus /></el-icon>新建任务
        </el-button>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="db-card list-card">
      <el-table :data="tasks" v-loading="loading" style="width: 100%" :header-cell-style="headerStyle">
        <el-table-column prop="name" label="任务名称" min-width="160">
          <template #default="{ row }">
            <div class="task-name">
              <div class="task-avatar">
                <el-icon><Operation /></el-icon>
              </div>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="调度" min-width="140">
          <template #default="{ row }">
            <el-tag size="small" round :type="scheduleTagType(row.schedule)">
              {{ scheduleLabel(row.schedule) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="speed_mode" label="速度" width="80">
          <template #default="{ row }">
            {{ speedLabel(row.speed_mode) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" round :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="400" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status !== 'running'" size="small" type="primary" round @click="handleRun(row)">
              <el-icon><VideoPlay /></el-icon>执行
            </el-button>
            <el-button v-else size="small" type="warning" round @click="handleStop(row)">
              <el-icon><CircleClose /></el-icon>停止
            </el-button>
            <el-button size="small" round @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>编辑
            </el-button>
            <el-button size="small" round @click="viewHistory(row)">历史</el-button>
            <el-button size="small" round @click="handleExport(row)">导出</el-button>
            <el-button size="small" type="danger" plain round @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !tasks.length" description="还没有任务，去创建一个吧" />
    </div>

    <!-- 执行历史弹窗 -->
    <el-dialog v-model="historyVisible" title="执行历史" width="720px">
      <el-table :data="history" style="width: 100%">
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" round :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始时间" />
        <el-table-column prop="duration_ms" label="耗时(ms)" width="110" />
        <el-table-column label="报告" width="90">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openReport(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import type { Task, ScheduleConfig, Execution } from "@/types";
import { useTaskStore } from "@/stores/task";
import * as api from "@/api";

const router = useRouter();
const taskStore = useTaskStore();
const { tasks, loading } = storeToRefs(taskStore);
const { fetchTasks } = taskStore;

const historyVisible = ref(false);
const history = ref<Execution[]>([]);
const currentTaskId = ref("");

const headerStyle = {
  background: "#fafbfc",
  color: "#646a73",
  fontWeight: "500",
};

onMounted(fetchTasks);

function scheduleLabel(s: ScheduleConfig | undefined) {
  if (!s || s.type === "once") return "立即执行";
  if (s.type === "cron") return `Cron: ${s.expression}`;
  if (s.type === "interval") return `间隔: ${JSON.stringify(s.interval)}`;
  if (s.type === "date") return `定时: ${s.run_date}`;
  return s.type;
}

function scheduleTagType(s: ScheduleConfig | undefined) {
  if (!s || s.type === "once") return "info";
  return "warning";
}

function speedLabel(m: string) {
  return { fast: "快速", normal: "正常", slow: "缓慢" }[m] || m;
}

function statusLabel(s: string) {
  return { idle: "空闲", running: "运行中", success: "成功", failed: "失败", partial: "部分成功" }[s] || s;
}

function statusTagType(s: string) {
  return { idle: "info", running: "primary", success: "success", failed: "danger", partial: "warning" }[s] || "info";
}

async function handleRun(task: Task) {
  try {
    await taskStore.run(task.id);
    await fetchTasks();
    ElMessage.success("任务已开始执行");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "执行失败");
  }
}

async function handleStop(task: Task) {
  try {
    await api.stopTask(task.id);
    await fetchTasks();
    ElMessage.success("已发送停止指令");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "停止失败");
  }
}

async function viewHistory(task: Task) {
  currentTaskId.value = task.id;
  history.value = await api.getHistory(task.id);
  historyVisible.value = true;
}

function openReport(exec: Execution) {
  historyVisible.value = false;
  router.push({ path: `/report/${currentTaskId.value}`, query: { run_id: exec.id } });
}

function handleEdit(task: Task) {
  router.push({ path: "/", query: { edit: task.id } });
}

function handleExport(task: Task) {
  const blob = new Blob([JSON.stringify(task.config, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${task.name}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function handleImport(file: File) {
  const text = await file.text();
  try {
    const cfg = JSON.parse(text);
    await taskStore.addTask(file.name.replace(/\.json$/, "") || cfg.task_name || "导入任务", cfg);
    ElMessage.success("导入成功");
  } catch (e) {
    ElMessage.error("导入失败，请检查 JSON 格式");
  }
  return false;
}

async function handleDelete(task: Task) {
  await ElMessageBox.confirm(`确认删除任务「${task.name}」？`, "提示", { type: "warning" });
  await taskStore.removeTask(task.id);
  ElMessage.success("已删除");
}
</script>

<style scoped>
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--db-text);
  margin: 0 0 6px;
}
.page-desc {
  font-size: 14px;
  color: var(--db-text-secondary);
  margin: 0;
}
.head-actions {
  display: flex;
  gap: 8px;
}

.list-card {
  padding: 8px 16px 16px;
}

.task-name {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 500;
}
.task-avatar {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: var(--db-primary-light);
  color: var(--db-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
}

.list-card :deep(.el-table) {
  --el-table-border-color: #f0f1f3;
}
.list-card :deep(.el-table th.el-table__cell) {
  border-radius: 0;
}
</style>
