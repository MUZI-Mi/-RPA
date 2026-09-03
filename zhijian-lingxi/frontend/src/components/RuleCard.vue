<template>
  <div class="rule-card">
    <div class="card-head">
      <el-tag size="small" :type="actionTagType">{{ actionLabel }}</el-tag>
      <span class="step-id">步骤 {{ step.step_id }}</span>
    </div>
    <div class="card-body">
      <div class="row" v-if="step.note">
        <span class="label">说明</span>
        <span class="value note-value">{{ step.note }}</span>
      </div>
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
  reload: "刷新网页",
  back: "后退",
  forward: "前进",
  close_tab: "关闭网页",
  foreach: "遍历列表",
  foreach_if: "逐条检查",
  set_var: "设置变量",
  goto: "转到步骤",
  if_text: "按文字判断",
  if_element: "按内容判断",
  if_var: "按结果判断",
  ocr: "OCR 读图",
  llm_extract: "AI 抽取",
  export: "导出报表",
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
    reload: "primary",
    close_tab: "danger",
    foreach_if: "primary",
    set_var: "warning",
    goto: "warning",
    if_text: "danger",
    if_element: "danger",
    if_var: "danger",
    ocr: "info",
    llm_extract: "info",
    export: "primary",
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
    less: "小于",
    less_equals: "小于等于",
    greater: "大于",
    greater_equals: "大于等于",
    set: "设为",
    inc: "加",
    dec: "减",
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
    case "reload":
      return "刷新当前网页";
    case "back":
      return "浏览器后退一页";
    case "forward":
      return "浏览器前进一页";
    case "close_tab":
      return a.close_target ? `关闭「${a.close_target}」这个网页` : "关闭当前网页，回到列表页";
    case "foreach":
      return `逐一打开列表「${a.selector || ""}」${a.next_selector ? `，每页点「${a.next_selector}」翻页` : "（不翻页）"}`;
    case "foreach_if":
      return `逐条检查「${a.selector || ""}」：含「${a.match_text || ""}」${a.click_selector ? `的项点「${a.click_selector}」` : "的项打开"}，其余跳过${a.next_selector ? `；每页点「${a.next_selector}」翻页` : ""}`;
    case "set_var":
      return `${a.var || ""} ${opLabels[a.op || "set"]} ${a.value ?? ""}`;
    case "goto":
      return `接着做：${to(a.target)}`;
    case "if_text":
      return `出现「${a.text || ""}」 → 满足:${to(a.goto_if_found)}，不满足:${to(a.goto_if_not)}`;
    case "if_element":
      return `有「${a.selector || ""}」 → 满足:${to(a.goto_if_found)}，不满足:${to(a.goto_if_not)}`;
    case "if_var":
      return `${a.var || ""} ${opLabels[a.op || "contains"] || "包含"} "${a.value || ""}" → 满足:${to(a.goto_if_found)}，不满足:${to(a.goto_if_not)}`;
    case "ocr":
      return `${a.ocr_source === "page" ? "整页" : "元素「" + (a.selector || "") + "」"}截图读文字${a.save_as ? ` → ${a.save_as}` : ""}`;
    case "llm_extract":
      return `从${a.var ? "变量「" + a.var + "」" : (a.selector ? "页面" : "文字")}抽取字段：${a.fields || ""}${a.save_as ? ` → ${a.save_as}` : ""}`;
    case "export":
      return `导出报表（${a.export_format || "csv"}）${a.export_filename ? `：${a.export_filename}` : ""}`;
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
.note-value {
  font-weight: 600;
  color: #529b2e;
}
.card-foot {
  margin-top: 8px;
  text-align: right;
}
</style>