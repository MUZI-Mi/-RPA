<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-head">
      <div>
        <h2 class="page-title">模板中心</h2>
        <p class="page-desc">{{ pageDesc }}</p>
      </div>
      <div class="head-actions">
        <el-button round @click="fetchList">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-upload
          :show-file-list="false"
          :before-upload="beforeUpload"
          accept=".xlsx,.xls,.docx"
        >
          <el-button type="primary" round>
            <el-icon><Upload /></el-icon>上传模板
          </el-button>
        </el-upload>
      </div>
    </div>

    <!-- 使用说明 -->
    <div class="db-card hint-card">
      <div class="hint-title">
        <el-icon><InfoFilled /></el-icon>怎么用模板？
      </div>
      <ol class="hint-list">
        <li>在 Excel / Word 里把要填数据的地方写成 <code>{{ fieldPh }}</code>（如 <code>{{ streetPh }}</code>）；</li>
        <li>在表格数据要展开的地方写 <code>{{ rowsPh }}</code>（仅 Excel，数据行从此处开始向下展开）；</li>
        <li>上传到模板中心，然后在任务的「导出报表」步骤里选择这个模板。</li>
      </ol>
    </div>

    <!-- 列表 -->
    <div class="db-card list-card">
      <el-table :data="items" v-loading="loading" style="width: 100%" :header-cell-style="headerStyle">
        <el-table-column label="模板名" min-width="160">
          <template #default="{ row }">
            <div class="tpl-name">
              <div class="tpl-icon">
                <el-icon><Files /></el-icon>
              </div>
              <div>
                <div class="tpl-title">{{ row.name }}</div>
                <div v-if="row.description" class="tpl-desc">{{ row.description }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" round :type="row.original_name.endsWith('.xlsx') || row.original_name.endsWith('.xls') ? 'success' : 'primary'">
              {{ row.original_name.split('.').pop()?.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="90">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="uploader" label="上传人" width="110" />
        <el-table-column prop="created_at" label="上传时间" width="150" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" round @click="download(row)">下载</el-button>
            <el-button size="small" type="danger" plain round @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" description="还没有模板，点右上角上传一个" />
    </div>

    <!-- 上传信息弹窗 -->
    <el-dialog v-model="uploadVisible" title="模板信息" width="480px">
      <el-form label-width="80px">
        <el-form-item label="模板名">
          <el-input v-model="uploadForm.name" :placeholder="defaultName" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="uploadForm.description" type="textarea" :rows="2" placeholder="这个模板填什么数据（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button round @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" round :loading="uploading" @click="confirmUpload">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { TemplateItem } from "@/types";
import * as api from "@/api";

const items = ref<TemplateItem[]>([]);
const loading = ref(false);
const uploading = ref(false);
const uploadVisible = ref(false);
const defaultName = ref("");
const pendingFile = ref<File | null>(null);
const uploadForm = reactive({ name: "", description: "" });

const headerStyle = { background: "#fafbfc", color: "#646a73", fontWeight: "500" };

// 占位符示例文字（{{ }} 在模板里需经变量渲染，避免被 Vue 当插值解析）
const fieldPh = "{{字段名}}";
const streetPh = "{{街道}}";
const rowsPh = "{{__rows__}}";
const pageDesc = "上传政务报表模板（Excel / Word），任务里用 {{占位符}} 自动填充数据";

onMounted(fetchList);

async function fetchList() {
  loading.value = true;
  try {
    items.value = await api.getTemplates();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载失败");
  } finally {
    loading.value = false;
  }
}

function formatSize(n?: number) {
  if (!n) return "—";
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / 1024 / 1024).toFixed(1) + " MB";
}

function beforeUpload(file: File) {
  pendingFile.value = file;
  defaultName.value = file.name.replace(/\.(xlsx|xls|docx)$/i, "");
  uploadForm.name = "";
  uploadForm.description = "";
  uploadVisible.value = true;
  return false; // 阻止默认上传，先填信息
}

async function confirmUpload() {
  if (!pendingFile.value) return;
  uploading.value = true;
  const fd = new FormData();
  fd.append("file", pendingFile.value);
  fd.append("name", uploadForm.name.trim() || defaultName.value);
  fd.append("description", uploadForm.description.trim());
  try {
    const res = await api.uploadTemplate(fd);
    ElMessage.success(`模板「${res.name}」上传成功`);
    uploadVisible.value = false;
    fetchList();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "上传失败");
  } finally {
    uploading.value = false;
  }
}

function download(row: TemplateItem) {
  window.open(api.downloadTemplateUrl(row.id), "_blank");
}

async function remove(row: TemplateItem) {
  await ElMessageBox.confirm(`确认删除模板「${row.name}」？`, "提示", { type: "warning" });
  try {
    await api.deleteTemplate(row.id);
    ElMessage.success("已删除");
    fetchList();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败");
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
.hint-card {
  padding: 14px 18px;
  margin-bottom: 16px;
  background: #f8faff;
  border-color: #dbe7ff;
}
.hint-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--db-primary);
  margin-bottom: 6px;
}
.hint-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--db-text-secondary);
  line-height: 1.9;
}
.hint-list code {
  background: #eef2ff;
  color: var(--db-primary);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}
.list-card {
  padding: 8px 16px 16px;
}
.tpl-name {
  display: flex;
  align-items: center;
  gap: 10px;
}
.tpl-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--db-primary-light);
  color: var(--db-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  flex-shrink: 0;
}
.tpl-title {
  font-weight: 500;
  color: var(--db-text);
}
.tpl-desc {
  font-size: 12px;
  color: var(--db-text-muted);
  margin-top: 2px;
}
</style>
