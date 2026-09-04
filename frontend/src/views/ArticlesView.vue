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
    <el-dialog v-model="genVisible" title="AI 生成文章（Mock 模式）" width="480">
      <el-input v-model="topic" placeholder="例如：海淀幼升小攻略" />
      <el-select v-model="genModel" style="width:100%;margin-top:12px">
        <el-option v-for="m in models" :key="m.id" :value="m.id" :label="m.name" />
      </el-select>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="doGenerate">生成</el-button>
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
import { ElMessage } from 'element-plus'
import { generateArticle, listModels, myArticles, publishArticle, type Article, type ModelInfo } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const articles = ref<Article[]>([])
const models = ref<ModelInfo[]>([])
const loading = ref(false)
const genVisible = ref(false)
const generating = ref(false)
const topic = ref('')
const genModel = ref('doubao-pro')
const previewVisible = ref(false)
const preview = ref<Article | null>(null)

function render(md: string) {
  return md.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\n/g, '<br/>')
}

async function refresh() {
  loading.value = true
  try { articles.value = await myArticles() } finally { loading.value = false }
}

async function doGenerate() {
  if (!topic.value.trim()) return ElMessage.warning('请输入主题')
  generating.value = true
  try {
    const { article } = await generateArticle({ topic: topic.value.trim(), model_id: genModel.value })
    ElMessage.success(`生成完成：${article.title}（作者已绑定 ${auth.user?.username}）`)
    genVisible.value = false
    topic.value = ''
    await refresh()
  } finally { generating.value = false }
}

async function publish(row: Article) {
  await publishArticle(row.id)
  ElMessage.success('发布成功（已过机审 stub）')
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
</style>
