<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-head">
      <div>
        <h2 class="page-title">审计日志</h2>
        <p class="page-desc">记录操作人、时间、对象、类型，满足留痕与追责要求</p>
      </div>
      <div class="head-actions">
        <el-button round @click="fetchList">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button type="primary" round :href="exportUrl" @click="handleExport">
          <el-icon><Download /></el-icon>导出 CSV
        </el-button>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="db-card filter-card">
      <el-form inline>
        <el-form-item label="操作人">
          <el-input v-model="filters.operator" placeholder="姓名" clearable style="width: 130px" @keyup.enter="fetchList" />
        </el-form-item>
        <el-form-item label="操作类型">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width: 150px">
            <el-option v-for="a in actionOptions" :key="a.value" :label="a.label" :value="a.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="对象类型">
          <el-select v-model="filters.target_type" placeholder="全部" clearable style="width: 130px">
            <el-option label="任务" value="task" />
            <el-option label="审核" value="review" />
            <el-option label="模板" value="template" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="filters.start"
            type="date"
            value-format="YYYY-MM-DD 00:00:00"
            placeholder="选择日期"
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="filters.end"
            type="date"
            value-format="YYYY-MM-DD 23:59:59"
            placeholder="选择日期"
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" round @click="fetchList">
            <el-icon><Search /></el-icon>查询
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 列表 -->
    <div class="db-card list-card">
      <el-table :data="items" v-loading="loading" style="width: 100%" :header-cell-style="headerStyle">
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column prop="operator" label="操作人" width="110" />
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <el-tag size="small" round>{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对象类型" width="100">
          <template #default="{ row }">
            {{ targetLabel(row.target_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="target_id" label="对象 ID" min-width="220" show-overflow-tooltip />
        <el-table-column label="详情" min-width="180">
          <template #default="{ row }">
            <span v-if="row.detail" class="detail-text">{{ prettyDetail(row.detail) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" description="暂无审计记录" />
      <div v-if="total > pageSize" class="pager">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="(p: number) => { page = p; fetchList(); }"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus";
import type { AuditItem } from "@/types";
import * as api from "@/api";

const items = ref<AuditItem[]>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = 20;

const filters = reactive<{
  operator: string;
  action: string;
  target_type: string;
  start: string;
  end: string;
}>({ operator: "", action: "", target_type: "", start: "", end: "" });

const headerStyle = { background: "#fafbfc", color: "#646a73", fontWeight: "500" };

const actionOptions = [
  { value: "create_task", label: "创建任务" },
  { value: "update_task", label: "修改任务" },
  { value: "delete_task", label: "删除任务" },
  { value: "run_task", label: "执行任务" },
  { value: "review_approve", label: "审核通过" },
  { value: "review_reject", label: "审核驳回" },
  { value: "review_update", label: "审核修改" },
  { value: "upload_template", label: "上传模板" },
  { value: "delete_template", label: "删除模板" },
];

const exportUrl = computed(() => {
  return api.exportAuditLogs({
    operator: filters.operator || undefined,
    action: filters.action || undefined,
    target_type: filters.target_type || undefined,
    start: filters.start || undefined,
    end: filters.end || undefined,
  });
});

onMounted(fetchList);

async function fetchList() {
  loading.value = true;
  try {
    const res = await api.getAuditLogs({
      operator: filters.operator || undefined,
      action: filters.action || undefined,
      target_type: filters.target_type || undefined,
      start: filters.start || undefined,
      end: filters.end || undefined,
      page: page.value,
      page_size: pageSize,
    });
    items.value = res.items;
    total.value = res.total;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载失败");
  } finally {
    loading.value = false;
  }
}

function actionLabel(a: string) {
  return actionOptions.find((x) => x.value === a)?.label || a;
}
function targetLabel(t: string) {
  return { task: "任务", review: "审核", template: "模板" }[t] || t;
}
function prettyDetail(d: any) {
  try {
    const obj = typeof d === "string" ? JSON.parse(d) : d;
    return Object.entries(obj)
      .map(([k, v]) => `${k}=${v}`)
      .join("，");
  } catch {
    return String(d);
  }
}

function handleExport() {
  // 由 <a :href> 直接触发下载；本地后端返回 CSV 附件
  ElMessage.success("正在导出审计日志…");
}
</script>

<style scoped>
.page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 16px 24px 24px;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-title {
  font-size: 36px;
  font-weight: 600;
  color: var(--db-text);
  margin: 0 0 6px;
}
.page-desc {
  font-size: 18px;
  color: var(--db-text-secondary);
  margin: 0;
}
.head-actions {
  display: flex;
  gap: 8px;
}
.filter-card {
  padding: 14px 16px;
  margin-bottom: 16px;
}
.filter-card :deep(.el-form-item) {
  margin-bottom: 8px;
}
.list-card {
  padding: 8px 16px 16px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
.muted {
  color: var(--db-text-muted);
}
.detail-text {
  font-size: 13px;
  color: var(--db-text-secondary);
}
</style>
