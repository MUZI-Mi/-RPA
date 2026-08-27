<template>
  <el-dialog
    :model-value="modelValue"
    :title="`编辑步骤 ${step?.step_id || ''}`"
    width="600px"
    @update:model-value="$emit('update:modelValue', $event)"
    @close="$emit('update:modelValue', false)"
  >
    <el-form :model="form" label-width="90px" label-position="left">
      <el-form-item label="执行时机">
        <el-select v-model="form.condition.type" style="width: 100%">
          <el-option label="直接执行" value="always" />
          <el-option label="等页面加载完" value="page_load" />
          <el-option label="等内容出现" value="element_visible" />
          <el-option label="等文字出现" value="text_appears" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.condition.type === 'element_visible'" label="等待的内容">
        <el-input v-model="form.condition.selector" placeholder="按钮文字或页面位置" />
      </el-form-item>
      <el-form-item v-if="form.condition.type === 'text_appears'" label="要等的文字">
        <el-input v-model="form.condition.text" placeholder="要出现的文字" />
      </el-form-item>
      <el-form-item v-if="['element_visible', 'text_appears'].includes(form.condition.type)" label="最长等待(毫秒)">
        <el-input-number v-model="form.condition.timeout" :min="0" :step="1000" />
      </el-form-item>

      <el-divider />

      <el-form-item label="动作类型">
        <el-select v-model="form.action.type" style="width: 100%">
          <el-option label="打开网页" value="open" />
          <el-option label="点击元素" value="click" />
          <el-option label="输入内容" value="input" />
          <el-option label="选择下拉项" value="select" />
          <el-option label="上传文件" value="upload" />
          <el-option label="滚动页面" value="scroll" />
          <el-option label="提取数据" value="extract" />
          <el-option label="等待" value="wait" />
          <el-option label="悬停" value="hover" />
          <el-option label="按键" value="press_key" />
          <el-option label="——按条件自动处理——" value="__divider__" disabled />
          <el-option label="转到指定步骤" value="goto" />
          <el-option label="按页面文字判断" value="if_text" />
          <el-option label="按页面内容判断" value="if_element" />
          <el-option label="按提取结果判断" value="if_var" />
        </el-select>
      </el-form-item>

      <el-form-item v-if="needsSelector" label="操作目标">
        <el-input v-model="form.action.selector" placeholder="按钮文字或页面位置" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'open'" label="网址">
        <el-input v-model="form.action.url" placeholder="https://example.com" />
      </el-form-item>
      <el-form-item v-if="['input', 'select'].includes(form.action.type)" label="值">
        <el-input v-model="form.action.value" placeholder="要输入的内容" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'extract'" label="提取类型">
        <el-select v-model="form.action.extract_type" style="width: 100%">
          <el-option label="文本" value="text" />
          <el-option label="属性" value="attribute" />
          <el-option label="HTML" value="inner_html" />
          <el-option label="值" value="value" />
          <el-option label="数量" value="count" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.action.type === 'extract'" label="保存为">
        <el-input v-model="form.action.save_as" placeholder="给结果起个名字" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'wait'" label="秒数">
        <el-input-number v-model="form.action.value" :min="0" :step="1" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'scroll'" label="像素">
        <el-input-number v-model="form.action.amount" :step="100" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'press_key'" label="按键">
        <el-input v-model="form.action.keys" placeholder="Enter / Tab" />
      </el-form-item>

      <!-- 按条件自动处理 -->
      <el-form-item v-if="form.action.type === 'goto'" label="接着做">
        <el-select v-model="form.action.target" style="width: 100%">
          <el-option v-for="o in targetOptions" :key="String(o.value)" :label="o.label" :value="o.value" />
        </el-select>
      </el-form-item>

      <el-form-item v-if="form.action.type === 'if_text'" label="要找的文字">
        <el-input v-model="form.action.text" placeholder="页面里要出现的文字" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'if_element'" label="要找的按钮/内容">
        <el-input v-model="form.action.selector" placeholder="例如：确定、下一页" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'if_var'" label="判断哪个结果">
        <el-input v-model="form.action.var" placeholder="上一步「提取数据」保存的结果名" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'if_var'" label="如何判断">
        <el-select v-model="form.action.op" style="width: 100%">
          <el-option label="包含" value="contains" />
          <el-option label="等于" value="equals" />
          <el-option label="不包含" value="not_contains" />
          <el-option label="不等于" value="not_equals" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.action.type === 'if_var'" label="要符合的内容">
        <el-input v-model="form.action.value" placeholder="例如：对公" />
      </el-form-item>

      <el-form-item v-if="['if_text', 'if_element', 'if_var'].includes(form.action.type)" label="满足时">
        <el-select v-model="form.action.goto_if_found" style="width: 100%">
          <el-option v-for="o in targetOptions" :key="String(o.value)" :label="o.label" :value="o.value" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="['if_text', 'if_element', 'if_var'].includes(form.action.type)" label="不满足时">
        <el-select v-model="form.action.goto_if_not" style="width: 100%">
          <el-option v-for="o in targetOptions" :key="String(o.value)" :label="o.label" :value="o.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import type { Step } from "@/types";

const props = defineProps<{ modelValue: boolean; step: Step | null; steps?: Step[] }>();
const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "save", step: Step): void;
}>();

const form = reactive<Step>({ step_id: 0, condition: { type: "always" }, action: { type: "click" } });

const needsSelector = computed(() =>
  ["click", "input", "select", "upload", "extract", "hover"].includes(form.action.type)
);

// 跳转目标选项：结束执行 + 各步骤 id
const targetOptions = computed(() => {
  const list: { label: string; value: number | null }[] = [{ label: "结束处理", value: null }];
  (props.steps || [])
    .map((s) => s.step_id)
    .sort((a, b) => a - b)
    .forEach((id) => list.push({ label: `步骤 ${id}`, value: id }));
  return list;
});

watch(
  () => props.step,
  (s) => {
    if (s) Object.assign(form, JSON.parse(JSON.stringify(s)));
  },
  { immediate: true }
);

function save() {
  emit("save", JSON.parse(JSON.stringify(form)));
  emit("update:modelValue", false);
}
</script>