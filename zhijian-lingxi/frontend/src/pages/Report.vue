<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-head">
      <div>
        <h2 class="page-title">执行报告</h2>
        <p class="page-desc">查看任务执行的完整回放、截图与自愈记录</p>
      </div>
      <el-button round @click="$router.push('/tasks')">
        <el-icon><Back /></el-icon>返回任务
      </el-button>
    </div>

    <!-- 执行概要 -->
    <div v-if="execution" class="db-card summary-card">
      <div class="summary-grid">
        <div class="summary-item">
          <div class="summary-label">执行状态</div>
          <el-tag round :type="statusType">{{ statusLabel }}</el-tag>
        </div>
        <div class="summary-item">
          <div class="summary-label">开始时间</div>
          <div class="summary-value">{{ execution.start_time }}</div>
        </div>
        <div class="summary-item">
          <div class="summary-label">结束时间</div>
          <div class="summary-value">{{ execution.end_time || "—" }}</div>
        </div>
        <div class="summary-item">
          <div class="summary-label">总耗时</div>
          <div class="summary-value">{{ execution.duration_ms }}ms</div>
        </div>
      </div>
      <div v-if="execution.error_msg" class="error-summary">
        <el-icon><WarningFilled /></el-icon>
        <span>{{ execution.error_msg }}</span>
      </div>
    </div>

    <!-- 步骤回放 -->
    <div v-if="steps.length" class="db-card section-card">
      <div class="section-title">
        <el-icon><List /></el-icon>步骤回放
      </div>
      <StepTimeline :steps="steps" />
    </div>

    <!-- 关键截图 -->
    <div v-if="screenshots.length" class="db-card section-card">
      <div class="section-title">
        <el-icon><Picture /></el-icon>关键截图
      </div>
      <ScreenshotViewer :images="screenshots" />
    </div>

    <el-empty v-if="!execution && !loading" description="暂无报告，请先在任务页执行任务" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import type { Execution, StepLog } from "@/types";
import * as api from "@/api";
import StepTimeline from "@/components/StepTimeline.vue";
import ScreenshotViewer from "@/components/ScreenshotViewer.vue";

const route = useRoute();
const taskId = route.params.id as string;
const runId = route.query.run_id as string | undefined;

const execution = ref<Execution | null>(null);
const steps = ref<StepLog[]>([]);
const loading = ref(false);

const statusType = computed(() => {
  const s = execution.value?.status;
  return { success: "success", failed: "danger", partial: "warning", running: "primary" }[s || ""] || "info";
});

const statusLabel = computed(() => {
  const s = execution.value?.status;
  return { success: "成功", failed: "失败", partial: "部分成功", running: "运行中" }[s || ""] || s;
});

const screenshots = computed(() => {
  const imgs: { url: string; label: string }[] = [];
  steps.value.forEach((s) => {
    if (s.screenshot_before) imgs.push({ url: screenshotUrl(taskId, s.step_id, "before"), label: `步骤${s.step_id}-前` });
    if (s.screenshot_after) imgs.push({ url: screenshotUrl(taskId, s.step_id, "after"), label: `步骤${s.step_id}-后` });
  });
  return imgs;
});

function screenshotUrl(taskId: string, stepId: number, key: string) {
  return `/api/reports/${taskId}/${runId}/screenshots/${stepId}`;
}

async function load() {
  loading.value = true;
  try {
    let rid = runId;
    if (!rid) {
      const latest = await api.getLatestReport(taskId);
      rid = latest.run_id;
    }
    const detail = await api.getReportDetail(taskId, rid!);
    execution.value = detail.execution;
    steps.value = detail.steps;
  } catch (e) {
    // 无报告时静默
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.page {
  max-width: 900px;
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

.summary-card {
  padding: 20px 24px;
  margin-bottom: 16px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.summary-label {
  font-size: 12px;
  color: var(--db-text-muted);
  margin-bottom: 6px;
}
.summary-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--db-text);
}
.error-summary {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #fff1f0;
  color: #d03050;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 13px;
  margin-top: 16px;
  line-height: 1.5;
}

.section-card {
  padding: 20px 24px;
  margin-bottom: 16px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--db-text);
  margin-bottom: 16px;
}
.section-title .el-icon {
  color: var(--db-primary);
}
</style>
