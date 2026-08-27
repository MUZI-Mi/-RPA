<template>
  <el-timeline>
    <el-timeline-item
      v-for="s in steps"
      :key="s.step_id"
      :timestamp="`${s.duration_ms}ms`"
      :type="s.status === 'success' ? 'success' : 'danger'"
      placement="top"
    >
      <div class="step-line">
        <el-tag size="small" :type="s.status === 'success' ? 'success' : 'danger'">
          {{ actionLabel(s.action_type) }}
        </el-tag>
        <span class="target">{{ s.target_element || "—" }}</span>
      </div>
      <div v-if="s.page_url" class="page-url">
        <el-icon><Link /></el-icon>
        <a :href="s.page_url" target="_blank" rel="noopener">{{ s.page_url }}</a>
      </div>
      <div v-if="s.healing_actions?.length" class="healing">
        <el-icon><RefreshRight /></el-icon>
        <span>{{ s.healing_actions.join(" → ") }}</span>
      </div>
      <div v-if="s.error_info" class="error">{{ s.error_info }}</div>
      <div v-if="s.extracted !== undefined && s.extracted !== null" class="extract">
        提取结果：{{ s.extracted }}
      </div>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
import type { StepLog } from "@/types";

defineProps<{ steps: StepLog[] }>();

const actionLabels: Record<string, string> = {
  open: "打开网页",
  click: "点击",
  input: "输入",
  select: "选择",
  upload: "上传",
  scroll: "滚动",
  extract: "提取",
  wait: "等待",
  hover: "悬停",
  press_key: "按键",
  goto: "转到步骤",
  if_text: "按文字判断",
  if_element: "按内容判断",
  if_var: "按结果判断",
};

function actionLabel(type: string) {
  return actionLabels[type] || type;
}
</script>

<style scoped>
.step-line {
  display: flex;
  align-items: center;
  gap: 8px;
}
.target {
  color: #666;
  font-size: 13px;
  word-break: break-all;
}
.healing {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #b88230;
  font-size: 12px;
  margin-top: 4px;
}
.page-url {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  margin-top: 4px;
}
.page-url a {
  color: var(--db-primary, #2e6ef5);
  text-decoration: none;
  word-break: break-all;
}
.page-url a:hover {
  text-decoration: underline;
}
.error {
  color: #d03050;
  font-size: 12px;
  margin-top: 4px;
}
.extract {
  background: #f0f7ff;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  margin-top: 4px;
}
</style>