<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-head">
      <div>
        <h2 class="page-title">审核队列</h2>
        <p class="page-desc">AI 判断出的异常/低置信度数据，人工核对后决定「通过 / 驳回 / 修改」</p>
      </div>
      <div class="head-actions">
        <el-button round @click="fetchList">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="db-card filter-card">
      <div class="filter-bar">
        <el-radio-group v-model="filterStatus" @change="fetchList">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="pending">待审核</el-radio-button>
          <el-radio-button value="approved">已通过</el-radio-button>
          <el-radio-button value="rejected">已驳回</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- 列表 -->
    <div class="db-card list-card">
      <el-table :data="items" v-loading="loading" style="width: 100%" :header-cell-style="headerStyle">
        <el-table-column prop="created_at" label="进入时间" width="150" />
        <el-table-column label="来源" width="140">
          <template #default="{ row }">
            <el-tag size="small" round>{{ sourceLabel(row.source) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              round
              :type="row.confidence == null ? 'info' : row.confidence >= 0.75 ? 'success' : 'warning'"
            >
              {{ row.confidence == null ? "—" : (row.confidence * 100).toFixed(0) + "%" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="异常问题" min-width="220">
          <template #default="{ row }">
            <div v-if="row.compliance_issues && row.compliance_issues.length">
              <el-tag
                v-for="(issue, i) in row.compliance_issues"
                :key="i"
                size="small"
                type="danger"
                class="issue-tag"
              >
                {{ issue }}
              </el-tag>
            </div>
            <span v-else class="muted">（无明确异常，低置信度）</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" round :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" round @click="openDetail(row)">查看</el-button>
            <el-button v-if="row.status === 'pending'" size="small" round @click="handleApprove(row)">通过</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" description="暂无待处理数据" />
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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="审核详情" width="760px" top="6vh">
      <template v-if="current">
        <div class="detail-block">
          <div class="detail-title">AI 判定</div>
          <div class="detail-ai">
            <div v-if="current.ai_result" class="ai-card">
              <template v-if="current.ai_result.summary">
                <div class="ai-summary">{{ current.ai_result.summary }}</div>
                <div v-if="current.ai_result.confidence != null" class="ai-meta">
                  置信度：{{ (current.ai_result.confidence * 100).toFixed(0) }}%
                </div>
              </template>
              <pre v-else>{{ pretty(current.ai_result) }}</pre>
            </div>
            <div v-if="current.compliance_issues && current.compliance_issues.length" class="issues">
              <el-tag
                v-for="(issue, i) in current.compliance_issues"
                :key="i"
                type="danger"
                size="small"
                class="issue-tag"
              >
                {{ issue }}
              </el-tag>
            </div>
          </div>
        </div>

        <div class="detail-block">
          <div class="detail-title">原始数据（人工核对用，仅存本机）</div>
          <pre class="raw-card">{{ pretty(current.raw_data) }}</pre>
        </div>

        <div v-if="current.status !== 'pending'" class="detail-block">
          <div class="detail-title">处理结果</div>
          <div class="result-line">
            状态：<el-tag size="small" round :type="statusTagType(current.status)">{{ statusLabel(current.status) }}</el-tag>
            <template v-if="current.operator"> · 操作人：{{ current.operator }}</template>
            <template v-if="current.review_note"> · 备注：{{ current.review_note }}</template>
          </div>
          <pre v-if="current.corrected_data" class="raw-card corrected">{{ pretty(current.corrected_data) }}</pre>
        </div>

        <template v-else>
          <el-input
            v-model="note"
            type="textarea"
            :rows="2"
            placeholder="审核备注（选填）"
          />
          <div class="detail-actions">
            <el-button round @click="handleReject(current)">驳回</el-button>
            <el-button round type="warning" @click="editVisible = true">修改后通过</el-button>
            <el-button type="primary" round @click="handleApprove(current)">通过</el-button>
          </div>
        </template>
      </template>
    </el-dialog>

    <!-- 修改数据弹窗 -->
    <el-dialog v-model="editVisible" title="修改后通过" width="640px">
      <el-input
        v-model="correctedText"
        type="textarea"
        :rows="10"
        placeholder="粘贴人工修正后的完整数据（JSON）"
      />
      <template #footer>
        <el-button round @click="editVisible = false">取消</el-button>
        <el-button type="primary" round @click="handleUpdate">确认并提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { ReviewItem } from "@/types";
import * as api from "@/api";

const items = ref<ReviewItem[]>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const filterStatus = ref("pending");

const detailVisible = ref(false);
const editVisible = ref(false);
const current = ref<ReviewItem | null>(null);
const note = ref("");
const correctedText = ref("");

const headerStyle = { background: "#fafbfc", color: "#646a73", fontWeight: "500" };

onMounted(fetchList);

async function fetchList() {
  loading.value = true;
  try {
    const res = await api.getReviews({
      status: filterStatus.value || undefined,
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

function sourceLabel(s?: string) {
  return (
    {
      llm_summarize: "AI 总结预警",
      data_clean: "数据清洗",
      llm_extract: "AI 抽取",
      manual: "人工",
    }[s || ""] || s || "—"
  );
}

function statusLabel(s: string) {
  return { pending: "待审核", approved: "已通过", rejected: "已驳回" }[s] || s;
}
function statusTagType(s: string) {
  return { pending: "warning", approved: "success", rejected: "danger" }[s] || "info";
}

function pretty(v: any) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function openDetail(row: ReviewItem) {
  current.value = row;
  note.value = "";
  correctedText.value = row.corrected_data ? pretty(row.corrected_data) : "";
  detailVisible.value = true;
}

async function handleApprove(row: ReviewItem) {
  try {
    await api.approveReview(row.id, { note: note.value || undefined });
    ElMessage.success("已通过");
    detailVisible.value = false;
    fetchList();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  }
}

async function handleReject(row: ReviewItem) {
  try {
    await ElMessageBox.confirm("确认驳回该条数据？", "提示", { type: "warning" });
    await api.rejectReview(row.id, { note: note.value || undefined });
    ElMessage.success("已驳回");
    detailVisible.value = false;
    fetchList();
  } catch (e: any) {
    if (e !== "cancel") ElMessage.error(e?.response?.data?.detail || "操作失败");
  }
}

async function handleUpdate() {
  let corrected: any;
  try {
    corrected = correctedText.value ? JSON.parse(correctedText.value) : null;
  } catch {
    ElMessage.error("修正数据不是合法 JSON，请检查后重试");
    return;
  }
  try {
    await api.updateReview(current.value!.id, {
      note: note.value || undefined,
      corrected_data: corrected,
    });
    ElMessage.success("已提交修正并通过");
    editVisible.value = false;
    detailVisible.value = false;
    fetchList();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  }
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
  font-size: 13px;
}
.issue-tag {
  margin: 2px 4px 2px 0;
}
.detail-block {
  margin-bottom: 16px;
}
.detail-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--db-text-muted);
  margin-bottom: 8px;
}
.ai-card {
  background: #f0f7ff;
  border: 1px solid #dbe9ff;
  border-radius: 10px;
  padding: 12px 14px;
}
.ai-summary {
  font-size: 14px;
  line-height: 1.6;
  color: var(--db-text);
}
.ai-meta {
  font-size: 12px;
  color: var(--db-text-muted);
  margin-top: 6px;
}
.issues {
  margin-top: 10px;
}
.raw-card {
  background: #fafbfc;
  border: 1px solid var(--db-border);
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.6;
  max-height: 260px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.raw-card.corrected {
  background: #f0fdf4;
  border-color: #c6f6d5;
}
.result-line {
  font-size: 14px;
  color: var(--db-text);
}
.detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
</style>
