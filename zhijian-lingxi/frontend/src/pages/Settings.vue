<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">设置</h2>
      <p class="page-desc">配置大模型、执行参数与通知方式</p>
    </div>

    <div class="settings-grid">
      <!-- 大模型配置 -->
      <div class="db-card section">
        <div class="section-head">
          <div class="section-icon llm"><el-icon><Cpu /></el-icon></div>
          <div>
            <div class="section-title">大模型配置</div>
            <div class="section-desc">用于自然语言解析与智能自愈</div>
          </div>
        </div>
        <el-form label-width="110px" label-position="left">
          <el-form-item label="模型来源">
            <el-select v-model="form.provider" style="width: 100%" @change="onProviderChange">
              <el-option
                v-for="p in providers"
                :key="p.id"
                :label="p.name"
                :value="p.id"
              />
            </el-select>
            <div v-if="currentProviderNote" class="provider-note">{{ currentProviderNote }}</div>
          </el-form-item>
          <el-form-item label="API Key">
            <div class="key-wrap">
              <el-input v-model="form.api_key" type="password" show-password :placeholder="keyPlaceholder" />
              <a
                v-if="currentRegisterUrl"
                class="key-link"
                :href="currentRegisterUrl"
                target="_blank"
                rel="noopener"
              >
                <el-icon><Link /></el-icon>获取免费 Key
              </a>
            </div>
          </el-form-item>
          <el-form-item label="Base URL">
            <el-input v-model="form.base_url" placeholder="https://api.siliconflow.cn/v1" />
          </el-form-item>
          <el-form-item label="文本模型">
            <el-input v-model="form.model" placeholder="Qwen/Qwen2.5-7B-Instruct" />
          </el-form-item>
          <el-form-item label="视觉模型">
            <el-input v-model="form.vl_model" placeholder="Qwen/Qwen2.5-VL-7B-Instruct" />
          </el-form-item>
          <el-form-item>
            <el-space>
              <el-button type="primary" round @click="save">保存</el-button>
              <el-button round :loading="testing" @click="test">测试连接</el-button>
            </el-space>
          </el-form-item>
        </el-form>
      </div>

      <!-- 执行设置 -->
      <div class="db-card section">
        <div class="section-head">
          <div class="section-icon exec"><el-icon><Odometer /></el-icon></div>
          <div>
            <div class="section-title">执行设置</div>
            <div class="section-desc">截图、报告与调度行为</div>
          </div>
        </div>
        <el-form label-width="110px" label-position="left">
          <el-form-item label="截图质量">
            <el-slider v-model="form.screenshot_quality" :min="10" :max="100" style="width: 220px" />
          </el-form-item>
          <el-form-item label="报告保留(天)">
            <el-input-number v-model="form.report_retention_days" :min="1" :max="365" />
          </el-form-item>
          <el-form-item label="错过补执行">
            <el-switch v-model="form.missed_run" />
          </el-form-item>
          <el-form-item label="显示执行窗口">
            <div class="key-wrap">
              <el-switch v-model="form.show_browser" />
              <div class="provider-note">勾选后执行任务会弹出可见浏览器窗口，方便观看自动化过程</div>
            </div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" round @click="save">保存</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 浏览器接管 -->
      <div class="db-card section full">
        <div class="section-head">
          <div class="section-icon exec"><el-icon><Monitor /></el-icon></div>
          <div>
            <div class="section-title">浏览器接管</div>
            <div class="section-desc">让程序在你自己的浏览器里操作（保留登录状态）</div>
          </div>
        </div>
        <el-form label-width="110px" label-position="left">
          <el-form-item label="浏览器方式">
            <el-radio-group v-model="form.browser_mode">
              <el-radio value="builtin">内置浏览器</el-radio>
              <el-radio value="attach">接管我的浏览器</el-radio>
            </el-radio-group>
          </el-form-item>
          <template v-if="form.browser_mode === 'attach'">
            <el-form-item label="调试地址">
              <el-input v-model="form.cdp_url" placeholder="http://127.0.0.1:9222" />
            </el-form-item>
            <el-form-item label="">
              <div class="key-wrap">
                <el-button round :loading="launching" @click="launchDebugBrowser">一键启动调试浏览器</el-button>
                <div class="provider-note">点击后弹出你本机的 Edge/Chrome 窗口（独立档案，登录一次即保持）。之后执行任务就会在这台浏览器里操作，不会新建无登录的内置浏览器。</div>
              </div>
            </el-form-item>
          </template>
          <el-form-item>
            <el-button type="primary" round @click="save">保存</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 合规与安全 -->
      <div class="db-card section full">
        <div class="section-head">
          <div class="section-icon audit"><el-icon><Lock /></el-icon></div>
          <div>
            <div class="section-title">合规与安全</div>
            <div class="section-desc">PII 脱敏、人工审核与操作留痕</div>
          </div>
        </div>
        <el-form label-width="110px" label-position="left">
          <el-form-item label="操作人姓名">
            <div class="key-wrap">
              <el-input v-model="form.operator_name" placeholder="用于审计日志记录操作人" style="max-width: 280px" />
              <div class="provider-note">所有操作会以这个姓名留痕，方便追责</div>
            </div>
          </el-form-item>
          <el-form-item label="PII 脱敏">
            <div class="key-wrap">
              <el-switch v-model="form.pii_masking_enabled" />
              <div class="provider-note">开启后，送进 AI 的身份证/手机号/银行卡等敏感信息会先自动打码，AI 返回后再还原，本机始终存明文</div>
            </div>
          </el-form-item>
          <el-form-item label="审核阈值">
            <div class="key-wrap">
              <el-slider v-model="form.review_threshold" :min="0.5" :max="0.95" :step="0.05" style="max-width: 280px" show-input />
              <div class="provider-note">AI 对数据的置信度低于此值时，自动进入「审核队列」等人工确认</div>
            </div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" round @click="save">保存</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 通知配置 -->
      <div class="db-card section full">
        <div class="section-head">
          <div class="section-icon notify"><el-icon><Bell /></el-icon></div>
          <div>
            <div class="section-title">通知配置</div>
            <div class="section-desc">任务完成或失败时推送提醒</div>
          </div>
        </div>
        <el-form label-width="110px" label-position="left">
          <el-form-item label="企业微信">
            <el-input v-model="form.wechat_webhook" placeholder="企业微信机器人 Webhook 地址" />
          </el-form-item>
          <el-form-item label="SMTP 主机">
            <el-input v-model="form.smtp_host" placeholder="smtp.example.com" />
          </el-form-item>
          <el-form-item label="SMTP 端口">
            <el-input-number v-model="form.smtp_port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="邮箱账号">
            <el-input v-model="form.smtp_user" />
          </el-form-item>
          <el-form-item label="授权码">
            <el-input v-model="form.smtp_password" type="password" show-password />
          </el-form-item>
          <el-form-item label="收件邮箱">
            <el-input v-model="form.smtp_to" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" round @click="save">保存全部</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
import * as api from "@/api";
import type { LLMProvider } from "@/types";

const form = reactive<Record<string, any>>({
  provider: "",
  api_key: "",
  base_url: "",
  model: "Qwen/Qwen2.5-7B-Instruct",
  vl_model: "Qwen/Qwen2.5-VL-7B-Instruct",
  screenshot_quality: 70,
  report_retention_days: 30,
  missed_run: true,
  show_browser: true,
  browser_mode: "builtin",
  cdp_url: "http://127.0.0.1:9222",
  wechat_webhook: "",
  smtp_host: "",
  smtp_port: 465,
  smtp_user: "",
  smtp_password: "",
  smtp_to: "",
  operator_name: "",
  pii_masking_enabled: true,
  review_threshold: 0.75,
});

const providers = ref<LLMProvider[]>([]);
const testing = ref(false);
const launching = ref(false);

const currentProvider = computed(() =>
  providers.value.find((p) => p.base_url === form.base_url) ||
  providers.value.find((p) => p.id === form.provider)
);
const currentProviderNote = computed(() => currentProvider.value?.note || "");
const currentRegisterUrl = computed(() => currentProvider.value?.register_url || "");
const keyPlaceholder = computed(() => {
  const name = currentProvider.value?.name || "所选平台";
  return `${name.replace(/（.*）/, "")}的 API Key`;
});

onMounted(async () => {
  try {
    const res = await api.getProviders();
    providers.value = res.providers;
  } catch (e) {
    // 忽略
  }
  try {
    const settings = await api.getSettings();
    Object.assign(form, settings);
    if (settings.screenshot_quality) form.screenshot_quality = Number(settings.screenshot_quality);
    if (settings.report_retention_days) form.report_retention_days = Number(settings.report_retention_days);
    if (settings.smtp_port) form.smtp_port = Number(settings.smtp_port);
    if (settings.missed_run !== undefined) form.missed_run = settings.missed_run !== "false";
    if (settings.show_browser !== undefined) form.show_browser = settings.show_browser === "true" || settings.show_browser === "1";
    if (settings.browser_mode) form.browser_mode = settings.browser_mode;
    if (settings.cdp_url) form.cdp_url = settings.cdp_url;
    // 合规相关（存储为字符串，需转换）
    if (settings.operator_name !== undefined) form.operator_name = settings.operator_name;
    if (settings.pii_masking_enabled !== undefined) {
      form.pii_masking_enabled = settings.pii_masking_enabled !== "false" && settings.pii_masking_enabled !== "0";
    }
    if (settings.review_threshold !== undefined) form.review_threshold = Number(settings.review_threshold);
    // 反向匹配 provider id
    if (settings.base_url) {
      const matched = providers.value.find((p) => p.base_url === settings.base_url);
      if (matched) form.provider = matched.id;
    }
  } catch (e) {
    // 忽略
  }
});

function onProviderChange(id: string) {
  const p = providers.value.find((x) => x.id === id);
  if (!p) return;
  if (p.id !== "custom") {
    form.base_url = p.base_url;
    form.model = p.model;
    form.vl_model = p.vl_model;
  }
}

async function save() {
  await api.updateSettings({ ...form });
  ElMessage.success("设置已保存");
}

async function test() {
  testing.value = true;
  try {
    const res = await api.testLLM();
    ElMessage.success(`连接成功：${res.reply}`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "连接失败");
  } finally {
    testing.value = false;
  }
}

async function launchDebugBrowser() {
  launching.value = true;
  try {
    const res = await api.launchBrowser();
    if (res.cdp_url) form.cdp_url = res.cdp_url;
    ElMessage.success(res.msg || "已启动浏览器");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "启动失败，请手动带参数启动浏览器");
  } finally {
    launching.value = false;
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
  margin-bottom: 16px;
}
.page-title {
  font-size: 26px;
  font-weight: 600;
  color: var(--db-text);
  margin: 0 0 6px;
}
.page-desc {
  font-size: 14px;
  color: var(--db-text-secondary);
  margin: 0;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.section {
  padding: 20px 24px;
}
.section.full {
  grid-column: 1 / -1;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.section-icon {
  width: 52px;
  height: 52px;
  border-radius: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  flex-shrink: 0;
}
.section-icon.llm {
  background: var(--db-primary-light);
  color: var(--db-primary);
}
.section-icon.exec {
  background: #e8f8ee;
  color: #18a058;
}
.section-icon.notify {
  background: #fff4e5;
  color: #f59f00;
}
.section-icon.audit {
  background: #eef0ff;
  color: #7c6cf5;
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--db-text);
}
.section-desc {
  font-size: 13px;
  color: var(--db-text-muted);
  margin-top: 2px;
}

.provider-note {
  font-size: 12px;
  color: var(--db-text-muted);
  line-height: 1.5;
  margin-top: 4px;
}

.key-wrap {
  width: 100%;
}
.key-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--db-primary);
  text-decoration: none;
  margin-top: 6px;
}
.key-link:hover {
  text-decoration: underline;
}

@media (max-width: 800px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
