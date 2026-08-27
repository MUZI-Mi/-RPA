<template>
  <div class="rule-card">
    <div class="card-head">
      <el-tag size="small" :type="actionTagType">{{ actionLabel }}</el-tag>
      <span class="step-id">步骤 {{ step.step_id }}</span>
    </div>
    <div class="card-body">
      <div class="row" v-if="conditionLabel">
        <span class="label">条件</span>
        <span class="value">{{ conditionLabel }}</span>
      </div>
      <div class="row">
        <span class="label">动作</span>
        <span class="value">{{ actionDescription }}</span>
      </div>
    </div>
    <div class="card-foot">
      <el-space>
        <el-button size="small" text @click="$emit('edit')">编辑</el-button>
        <el-button size="small" text type="danger" @click="$emit('delete')">删除</el-button>
      </el-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Step } from "@/types";

const props = defineProps<{ step: Step }>();

defineEmits<{ (e: "edit"): void; (e: "delete"): void }>();

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

const conditionLabels: Record<string, string> = {
  page_load: "等页面加载完",
  element_visible: "等内容出现",
  text_appears: "等文字出现",
  always: "直接执行",
};

const actionLabel = computed(() => actionLabels[props.step.action.type] || props.step.action.type);
const actionTagType = computed(() => {
  const map: Record<string, string> = {
    open: "primary",
    click: "success",
    input: "warning",
    extract: "info",
    wait: "info",
    goto: "warning",
    if_text: "danger",
    if_element: "danger",
    if_var: "danger",
  };
  return (map[props.step.action.type] || "info") as any;
});

const conditionLabel = computed(() => {
  const c = props.step.condition;
  if (!c || c.type === "always") return "";
  return conditionLabels[c.type] || c.type;
});

const actionDescription = computed(() => {
  const a = props.step.action;
  const to = (id?: number | null) => (id == null ? "结束处理" : `步骤 ${id}`);
  const opLabels: Record<string, string> = {
    contains: "包含",
    equals: "等于",
    not_contains: "不包含",
    not_equals: "不等于",
  };
  switch (a.type) {
    case "open":
      return a.url || "";
    case "click":
      return a.selector || a.text || "";
    case "input":
      return `${a.selector || ""} ← ${a.value || ""}`;
    case "extract":
      return `${a.selector || ""} (${a.extract_type || "text"})${a.save_as ? ` → ${a.save_as}` : ""}`;
    case "wait":
      return `${a.value || 1} 秒`;
    case "scroll":
      return `${a.amount || 300}px`;
    case "press_key":
      return a.keys || "";
    case "goto":
      return `接着做：${to(a.target)}`;
    case "if_text":
      return `出现「${a.text || ""}」 → 满足:${to(a.goto_if_found)}，不满足:${to(a.goto_if_not)}`;
    case "if_element":
      return `有「${a.selector || ""}」 → 满足:${to(a.goto_if_found)}，不满足:${to(a.goto_if_not)}`;
    case "if_var":
      return `${a.var || ""} ${opLabels[a.op || "contains"] || "包含"} "${a.value || ""}" → 满足:${to(a.goto_if_found)}，不满足:${to(a.goto_if_not)}`;
    default:
      return a.selector || a.value || "";
  }
});
</script>

<style scoped>
.rule-card {
  border: 1px solid var(--db-border);
  border-radius: 12px;
  padding: 12px 14px;
  background: #fff;
  margin-bottom: 8px;
  transition: all 0.2s;
}
.rule-card:hover {
  border-color: var(--db-primary);
  box-shadow: var(--db-shadow-hover);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.step-id {
  font-size: 12px;
  color: var(--db-text-muted);
}
.card-body .row {
  display: flex;
  gap: 8px;
  font-size: 13px;
  margin: 3px 0;
}
.label {
  color: var(--db-text-muted);
  min-width: 36px;
}
.value {
  color: var(--db-text);
  word-break: break-all;
}
.card-foot {
  margin-top: 8px;
  text-align: right;
}
</style>