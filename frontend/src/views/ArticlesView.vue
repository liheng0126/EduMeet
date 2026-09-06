<template>
  <div class="page">
    <header>
      <el-button text @click="$router.push('/')">← 返回工作台</el-button>
      <b>我的文章</b>
      <el-button type="primary" size="small" @click="genVisible = true">＋ AI 生成文章</el-button>
    </header>

    <el-table :data="articles" v-loading="loading" style="margin:16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" min-width="220" />
      <el-table-column prop="source" label="来源" width="120">
        <template #default="{ row }">{{ row.source === 'ai_generated' ? 'AI 生成' : '手动创作' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'published' ? 'success' : 'info'">
            {{ row.status === 'published' ? '已发布' : '草稿' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="view(row)">预览</el-button>
          <el-button size="small" type="success" :disabled="row.status === 'published'" @click="publish(row)">发布</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 生成对话框 -->
    <el-dialog v-model="genVisible" title="AI 生成文章" width="min(720px, 92vw)"
               :close-on-click-modal="!generating" :show-close="!generating">
      <el-input v-model="topic" maxlength="200" :disabled="generating"
                placeholder="例如：海淀幼升小攻略" />
      <el-select v-model="genModel" :disabled="generating" style="width:100%;margin-top:12px">
        <el-option v-for="m in models" :key="m.id" :value="m.id" :label="m.name" />
      </el-select>
      <div v-if="generationProgress" class="generation-progress">{{ generationProgress }}</div>
      <div v-if="streamContent" class="stream-preview md" v-html="render(streamContent)"></div>
      <template #footer>
        <el-button :disabled="generating" @click="genVisible = false">
          {{ generatedArticle ? '关闭' : '取消' }}
        </el-button>
        <el-button v-if="generating" type="danger" plain @click="stopGeneration">停止生成</el-button>
        <el-button v-else type="primary" :disabled="!topic.trim()" @click="doGenerate">
          {{ generatedArticle ? '重新生成' : '生成' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog v-model="previewVisible" :title="preview?.title" width="640">
      <div class="md" v-html="render(preview?.content_md || '')"></div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { generateArticleStream, listModels, myArticles, publishArticle, type Article, type ModelInfo } from '../api'

const articles = ref<Article[]>([])
const models = ref<ModelInfo[]>([])
const loading = ref(false)
const genVisible = ref(false)
const generating = ref(false)
const topic = ref('')
const genModel = ref('doubao-pro')
const previewVisible = ref(false)
const preview = ref<Article | null>(null)
const streamContent = ref('')
const generationProgress = ref('')
const generatedArticle = ref<Article | null>(null)
let generationAborter: AbortController | null = null

function render(md: string) {
  return DOMPurify.sanitize(marked.parse(md) as string)
}

async function refresh() {
  loading.value = true
  try { articles.value = await myArticles() } finally { loading.value = false }
}

async function doGenerate() {
  if (!topic.value.trim()) return ElMessage.warning('请输入主题')
  generating.value = true
  streamContent.value = ''
  generatedArticle.value = null
  generationProgress.value = '正在准备文章生成…'
  generationAborter = new AbortController()
  let streamFailed = false
  try {
    await generateArticleStream(
      { topic: topic.value.trim(), model_id: genModel.value },
      {
        onDelta: (text) => { streamContent.value += text },
        onProgress: (data) => {
          if (data.stage === 'done') {
            generatedArticle.value = data.article
            generationProgress.value = '生成完成，文章已保存为草稿'
          } else {
            generationProgress.value = data.detail || data.stage
          }
        },
        onError: (message) => {
          streamFailed = true
          generationProgress.value = `生成失败：${message}`
        },
      },
      generationAborter.signal,
    )
    if (generatedArticle.value) {
      ElMessage.success('文章已生成并保存为草稿')
      await refresh()
    } else if (!streamFailed) {
      throw new Error('文章流提前结束')
    }
  } catch (error: any) {
    if (error?.name === 'AbortError') generationProgress.value = '已停止生成，未保存草稿'
    else if (!streamFailed) generationProgress.value = '生成中断，请稍后重试'
  } finally {
    generating.value = false
    generationAborter = null
  }
}

function stopGeneration() { generationAborter?.abort() }

async function publish(row: Article) {
  await publishArticle(row.id)
  ElMessage.success('发布成功')
  await refresh()
}

const view = (row: Article) => { preview.value = row; previewVisible.value = true }

onMounted(async () => {
  models.value = await listModels()
  await refresh()
})
</script>

<style scoped>
.page { height: 100%; overflow-y: auto; }
header { display: flex; align-items: center; gap: 14px; padding: 14px 16px; background: #fff; border-bottom: 1px solid #e2e8f0; }
header b { flex: 1; }
.md { font-size: 14px; line-height: 1.8; max-height: 55vh; overflow-y: auto; }
.generation-progress { margin-top: 14px; color: #64748b; font-size: 13px; }
.stream-preview { min-height: 120px; margin-top: 10px; padding: 14px; border: 1px solid #e5e7eb;
  border-radius: 8px; background: #fafafa; }
.md :deep(h1), .md :deep(h2), .md :deep(h3) { margin: 12px 0 8px; font-size: 1.08em; }
.md :deep(p) { margin: 8px 0; }
.md :deep(ul), .md :deep(ol) { padding-left: 22px; }
</style>
