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
          <el-option label="刷新网页" value="reload" />
          <el-option label="后退" value="back" />
          <el-option label="前进" value="forward" />
          <el-option label="关闭当前网页" value="close_tab" />
          <el-option label="遍历并逐一打开列表" value="foreach" />
          <el-option label="逐条检查（命中才处理）" value="foreach_if" />
          <el-option label="OCR 读图（把图片/截图变文字）" value="ocr" />
          <el-option label="AI 抽取关键信息" value="llm_extract" />
          <el-option label="导出报表（数据文件）" value="export" />
          <el-option label="读取本地 Excel" value="read_excel" />
          <el-option label="读取本地 CSV" value="read_csv" />
          <el-option label="OCR 识别成表格" value="ocr_to_json" />
          <el-option label="数据清洗（去重/补空/统一格式）" value="data_clean" />
          <el-option label="AI 总结与异常预警" value="llm_summarize" />
          <el-option label="——按条件自动处理——" value="__divider__" disabled />
          <el-option label="转到指定步骤" value="goto" />
          <el-option label="按页面文字判断" value="if_text" />
          <el-option label="按页面内容判断" value="if_element" />
          <el-option label="按提取结果判断" value="if_var" />
          <el-option label="设置/增减变量" value="set_var" />
        </el-select>
      </el-form-item>

      <el-form-item v-if="needsSelector" label="操作目标">
        <el-input v-model="form.action.selector" placeholder="按钮文字或页面位置" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'open'" label="网址">
        <el-input v-model="form.action.url" placeholder="https://example.com" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'close_tab'" label="关闭哪个网页">
        <el-input
          v-model="form.action.close_target"
          placeholder="留空=关闭当前网页；或填要关闭网页的文字，如：番剧"
        />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'foreach'" label="要遍历的链接">
        <el-input
          v-model="form.action.selector"
          placeholder="页面上要逐一点开的元素，如：.announcement a 或 li a"
        />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'foreach'" label="下一页按钮">
        <el-input
          v-model="form.action.next_selector"
          placeholder="分页“下一页”按钮，如：a.nextPage；留空=不翻页"
        />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'foreach_if'" label="要检查的列表">
        <el-input
          v-model="form.action.selector"
          placeholder="页面上每条记录的位置，如：tbody tr 或 ul li"
        />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'foreach_if'" label="命中关键词">
        <el-input
          v-model="form.action.match_text"
          placeholder="记录里含这个字/词才处理，如：差旅；留空=全部处理"
        />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'foreach_if'" label="命中了点什么">
        <el-input
          v-model="form.action.click_selector"
          placeholder="命中那条记录里的按钮/链接，如：确认；留空=打开该记录链接"
        />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'foreach_if'" label="下一页按钮">
        <el-input
          v-model="form.action.next_selector"
          placeholder="分页“下一页”按钮，如：a.nextPage；留空=不翻页"
        />
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
      <el-form-item v-if="form.action.type === 'set_var'" label="变量名">
        <el-input v-model="form.action.var" placeholder="例如：i" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'set_var'" label="操作">
        <el-select v-model="form.action.op" style="width: 100%">
          <el-option label="设为" value="set" />
          <el-option label="加" value="inc" />
          <el-option label="减" value="dec" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.action.type === 'set_var'" label="数值">
        <el-input v-model="form.action.value" placeholder="设为：起始值；加/减：步长" />
      </el-form-item>

      <!-- OCR 读图 -->
      <el-form-item v-if="form.action.type === 'ocr'" label="识别范围">
        <el-select v-model="form.action.ocr_source" style="width: 100%">
          <el-option label="整页截图" value="page" />
          <el-option label="页面某块内容" value="element" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.action.type === 'ocr' && form.action.ocr_source === 'element'" label="要识别的内容">
        <el-input v-model="form.action.selector" placeholder="页面上的某块图片/文字位置，如：.contract-img" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'ocr'" label="保存为">
        <el-input v-model="form.action.save_as" placeholder="给识别出的文字起个名字" />
      </el-form-item>

      <!-- AI 抽取 -->
      <el-form-item v-if="form.action.type === 'llm_extract'" label="抽取来源">
        <el-select v-model="form.action._src" style="width: 100%" @change="onLlExtractSrcChange">
          <el-option label="上一步提取的变量" value="var" />
          <el-option label="直接从页面提取文字" value="page" />
          <el-option label="手工粘贴文字" value="text" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.action.type === 'llm_extract' && form.action._src === 'var'" label="变量名">
        <el-input v-model="form.action.var" placeholder="上一步提取保存的结果名" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'llm_extract' && form.action._src === 'page'" label="页面文字位置">
        <el-input v-model="form.action.selector" placeholder="要抽取的整块文字位置，如：.content" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'llm_extract' && form.action._src === 'text'" label="粘贴文字">
        <el-input v-model="form.action.text" type="textarea" :rows="3" placeholder="直接粘贴要抽取的文字" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'llm_extract'" label="要抽取的字段">
        <el-input v-model="form.action.fields" placeholder="逗号分隔，如：标题,日期,金额" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'llm_extract'" label="保存为">
        <el-input v-model="form.action.save_as" placeholder="给抽取结果起个名字" />
      </el-form-item>

      <!-- 导出报表 -->
      <el-form-item v-if="form.action.type === 'export'" label="导出格式">
        <el-select v-model="form.action.export_format" style="width: 100%">
          <el-option label="CSV（Excel 可打开）" value="csv" />
          <el-option label="JSON（原始数据）" value="json" />
          <el-option label="Excel (.xlsx)" value="xlsx" />
          <el-option label="Word (.docx)" value="docx" />
          <el-option label="PDF（打印上报）" value="pdf" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.action.type === 'export'" label="文件名">
        <el-input v-model="form.action.export_filename" placeholder="如：财务报告汇总；留空用任务名" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'export' && ['xlsx', 'docx'].includes(form.action.export_format || '')" label="套用模板">
        <el-input v-model="form.action.template_file" placeholder="模板中心的模板名，留空=自动生成" />
      </el-form-item>

      <!-- 读取本地 Excel -->
      <el-form-item v-if="form.action.type === 'read_excel'" label="文件路径">
        <el-input v-model="form.action.file_path" placeholder="本机 Excel 文件路径，如：D:\\报表\\人员名单.xlsx" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'read_excel'" label="工作表">
        <el-input v-model="form.action.sheet_name" placeholder="留空=第一个工作表" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'read_excel'" label="有表头">
        <el-switch v-model="form.action.has_header" />
      </el-form-item>

      <!-- 读取本地 CSV -->
      <el-form-item v-if="form.action.type === 'read_csv'" label="文件路径">
        <el-input v-model="form.action.file_path" placeholder="本机 CSV 文件路径" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'read_csv'" label="编码">
        <el-select v-model="form.action.encoding" style="width: 100%">
          <el-option label="UTF-8" value="utf-8" />
          <el-option label="GBK" value="gbk" />
          <el-option label="UTF-8 with BOM" value="utf-8-sig" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.action.type === 'read_csv'" label="分隔符">
        <el-select v-model="form.action.delimiter" style="width: 100%">
          <el-option label="逗号 ," value="," />
          <el-option label="制表符 Tab" value="\t" />
          <el-option label="分号 ;" value=";" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.action.type === 'read_csv'" label="有表头">
        <el-switch v-model="form.action.has_header" />
      </el-form-item>

      <!-- OCR 识别成表格 -->
      <el-form-item v-if="form.action.type === 'ocr_to_json'" label="识别范围">
        <el-select v-model="form.action.ocr_source" style="width: 100%">
          <el-option label="整页截图" value="page" />
          <el-option label="页面某块内容" value="element" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.action.type === 'ocr_to_json' && form.action.ocr_source === 'element'" label="要识别的内容">
        <el-input v-model="form.action.selector" placeholder="页面上的某块扫描件/图片位置，如：.contract-img" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'ocr_to_json'" label="表格字段">
        <el-input v-model="form.action.fields" placeholder="逗号分隔，如：姓名,身份证号,金额" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'ocr_to_json'" label="保存为">
        <el-input v-model="form.action.save_as" placeholder="给表格起个名字" />
      </el-form-item>

      <!-- 数据清洗 -->
      <el-form-item v-if="form.action.type === 'data_clean'" label="处理哪份数据">
        <el-input v-model="form.action.source" placeholder="变量名；留空=当前表格" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'data_clean'" label="去重列">
        <el-input v-model="cleanRules.dedup" placeholder="按哪些列去重，逗号分隔，如：姓名,身份证号" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'data_clean'" label="空值填充">
        <el-input v-model="cleanRules.fill" placeholder="列=填充值，用分号分隔，如：区县=浦东新区; 状态=正常" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'data_clean'" label="日期列">
        <el-input v-model="cleanRules.date" placeholder="要统一成 YYYY-MM-DD 的列，逗号分隔" />
      </el-form-item>

      <!-- AI 总结与异常预警 -->
      <el-form-item v-if="form.action.type === 'llm_summarize'" label="总结哪份数据">
        <el-input v-model="form.action.source" placeholder="变量名；留空=当前表格" />
      </el-form-item>
      <el-form-item v-if="form.action.type === 'llm_summarize'" label="每批条数">
        <el-input-number v-model="form.action.batch_size" :min="1" :max="50" />
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
          <el-option label="等于" value="equals" />
          <el-option label="包含" value="contains" />
          <el-option label="不等于" value="not_equals" />
          <el-option label="不包含" value="not_contains" />
          <el-option label="小于" value="less" />
          <el-option label="小于等于" value="less_equals" />
          <el-option label="大于" value="greater" />
          <el-option label="大于等于" value="greater_equals" />
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

// 数据清洗规则（界面拆分字段，保存时合并进 action.rules）
const cleanRules = reactive({ dedup: "", fill: "", date: "" });

function parseCleanRules() {
  const r: Record<string, any> = {};
  if (cleanRules.dedup.trim()) {
    r.dedup = cleanRules.dedup.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
  }
  if (cleanRules.fill.trim()) {
    const fill: Record<string, string> = {};
    cleanRules.fill.split(/[;；]/).forEach((pair) => {
      const idx = pair.indexOf("=");
      if (idx > 0) fill[pair.slice(0, idx).trim()] = pair.slice(idx + 1).trim();
    });
    if (Object.keys(fill).length) r.fill_empty = fill;
  }
  if (cleanRules.date.trim()) {
    r.date_format = cleanRules.date.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
  }
  return r;
}

function fillCleanRules(rules: any) {
  cleanRules.dedup = (rules?.dedup || []).join(",");
  const fill = rules?.fill_empty || {};
  cleanRules.fill = Object.entries(fill)
    .map(([k, v]) => `${k}=${v}`)
    .join("; ");
  cleanRules.date = (rules?.date_format || []).join(",");
}

// AI 抽取来源选择（_src 仅界面用，不随动作保存到后端）
function onLlExtractSrcChange(src: string) {
  const a = form.action as any;
  a.var = src === "var" ? a.var : "";
  a.selector = src === "page" ? a.selector : "";
  a.text = src === "text" ? a.text : "";
}

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
    if (s) {
      Object.assign(form, JSON.parse(JSON.stringify(s)));
      // 初始化 AI 抽取的来源显示
      const a = form.action as any;
      if (a.type === "llm_extract") {
        a._src = a.var ? "var" : a.selector ? "page" : a.text ? "text" : "var";
      }
      if (a.type === "data_clean") {
        fillCleanRules(a.rules);
      }
      // 新动作字段默认值
      if (a.type === "read_excel" && a.has_header === undefined) a.has_header = true;
      if (a.type === "read_csv") {
        if (a.has_header === undefined) a.has_header = true;
        if (!a.encoding) a.encoding = "utf-8";
        if (!a.delimiter) a.delimiter = ",";
      }
      if (a.type === "ocr_to_json" && !a.ocr_source) a.ocr_source = "page";
      if (a.type === "llm_summarize" && !a.batch_size) a.batch_size = 10;
    }
  },
  { immediate: true }
);

function save() {
  const out = JSON.parse(JSON.stringify(form)) as Step;
  if (out.action.type === "llm_extract") {
    delete (out.action as any)._src;
  }
  if (out.action.type === "data_clean") {
    out.action.rules = parseCleanRules();
  }
  emit("save", out);
  emit("update:modelValue", false);
}
</script>