<template>
  <div class="shell">
    <!-- 侧栏：会话历史（ChatGPT 式窄侧栏） -->
    <aside class="side">
      <div class="brand">EduMeet</div>
      <button class="new-chat" @click="newSession">
        <span class="plus">＋</span> 新会话
      </button>
      <div class="session-list">
        <div v-for="s in sessions" :key="s.id" class="session-item" :class="{ on: s.id === currentId }"
             @click="switchSession(s.id)">{{ s.title }}</div>
      </div>
      <div class="side-bottom">
        <div class="side-link" @click="$router.push('/articles')">📄 我的文章</div>
        <div class="user">{{ auth.user?.nickname || auth.user?.username }}
          <span class="logout" @click="auth.logout()">退出</span>
        </div>
      </div>
    </aside>

    <!-- 主区：对话 -->
    <main class="main">
      <div class="thread" ref="threadEl">
        <div class="col">
          <section v-if="!messages.length" class="empty-state">
            <div class="greet">今天想了解哪里的教育政策？</div>
            <p class="greet-sub">选择省市快速查询，或直接在下方输入你的问题</p>
            <div class="policy-grid">
              <button v-for="region in policyRegions" :key="region.name" type="button"
                      class="policy-card" :class="`tone-${region.tone}`"
                      :disabled="streaming" :aria-label="`查询${region.name}中小学教育政策`"
                      @click="askPolicy(region)">
                <span class="policy-mark">{{ region.short }}</span>
                <span class="policy-copy">
                  <strong>{{ region.name }}</strong>
                  <small>{{ region.topic }}</small>
                </span>
                <el-icon class="policy-arrow"><ArrowRight /></el-icon>
              </button>
            </div>
          </section>
          <template v-for="m in messages" :key="m.id ?? m._tmp">
            <!-- 用户：右对齐灰气泡 -->
            <div v-if="m.role === 'user'" class="row user">
              <div class="u-bubble">{{ m.content }}</div>
            </div>
            <!-- AI：全宽无气泡 Markdown -->
            <div v-else class="row ai">
              <div class="ai-head">EduMeet</div>
              <div class="ai-content md" v-html="renderMd(m.content)"></div>
              <button v-if="m.articleId" type="button" class="article-link" @click="openArticles">
                <el-icon><Document /></el-icon>
                已保存为文章草稿，前往我的文章
                <el-icon><ArrowRight /></el-icon>
              </button>
              <div v-if="m.citations?.length" class="cites">
                📎 来源：<a v-for="c in m.citations" :key="c.url" :href="c.url" target="_blank">{{ c.title }}</a>
              </div>
              <div class="ai-actions">
                <button class="act" title="复制" @click="copy(m.content)">⧉</button>
                <button class="act" title="重新生成（M1 迭代）" disabled>⟳</button>
              </div>
            </div>
          </template>
          <div v-if="progress" class="progress">{{ progress }}</div>
        </div>
      </div>

      <div class="composer-zone">
        <div class="mode-switch" role="tablist" aria-label="Agent 工作模式">
          <button type="button" role="tab" :aria-selected="mode === 'policy'"
                  :class="{ active: mode === 'policy' }" :disabled="streaming"
                  @click="mode = 'policy'">
            <el-icon><Search /></el-icon>政策查询
          </button>
          <button type="button" role="tab" :aria-selected="mode === 'article'"
                  :class="{ active: mode === 'article' }" :disabled="streaming"
                  @click="mode = 'article'">
            <el-icon><EditPen /></el-icon>文章撰写
          </button>
          <span class="custom-wrap" title="自定义功能尚未体现，敬请期待">
            <button type="button" role="tab" aria-selected="false" disabled>
              <el-icon><Setting /></el-icon>自定义
              <small>敬请期待</small>
            </button>
          </span>
        </div>
        <div class="composer">
          <textarea ref="taEl" v-model="input" rows="1" :placeholder="inputPlaceholder"
                    :maxlength="mode === 'article' ? 200 : undefined"
                    @keydown.enter.exact.prevent="send" @input="autoGrow"></textarea>
          <button v-if="streaming" class="send stop" title="停止" @click="stop">■</button>
          <button v-else class="send" :disabled="!input.trim()" title="发送" @click="send">↑</button>
          <el-dropdown trigger="click" @command="modelId = $event">
            <button class="model-chip" type="button" title="切换模型">{{ currentModel?.name || '选择模型' }}
              <span v-if="!currentModel?.free" class="tag">会员</span> ▾</button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="m in models" :key="m.id" :command="m.id"
                                  :class="{ picked: m.id === modelId }">
                  {{ m.name }} · {{ m.vendor }}{{ m.free ? '（免费）' : '' }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="disclaimer">AI 也可能会犯错，请核查重要信息。</div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import DOMPurify from 'dompurify'
import { ArrowRight, Document, EditPen, Search, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { useRouter } from 'vue-router'
import { chatStream, createSession, generateArticleStream, listMessages, listModels, listSessions, type Conversation, type MessageItem, type ModelInfo } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const sessions = ref<Conversation[]>([])
const currentId = ref<number | null>(null)
type WorkspaceMessage = MessageItem & { _tmp?: number; articleId?: number }
const messages = ref<WorkspaceMessage[]>([])
const models = ref<ModelInfo[]>([])
const modelId = ref('deepseek-chat') // 默认模型：DeepSeek
const mode = ref<'policy' | 'article'>('policy')
const input = ref('')
const streaming = ref(false)
const progress = ref('')
const threadEl = ref<HTMLElement>()
const taEl = ref<HTMLTextAreaElement>()
let aborter: AbortController | null = null

type PolicyRegion = { name: string; short: string; topic: string; tone: string }
const policyRegions: PolicyRegion[] = [
  { name: '北京市', short: '京', topic: '义务教育入学', tone: 'red' },
  { name: '上海市', short: '沪', topic: '升学与学区政策', tone: 'blue' },
  { name: '广东省', short: '粤', topic: '随迁子女入学', tone: 'green' },
  { name: '江苏省', short: '苏', topic: '招生与考试政策', tone: 'gold' },
  { name: '浙江省', short: '浙', topic: '义务教育招生', tone: 'cyan' },
  { name: '四川省', short: '川', topic: '中小学入学政策', tone: 'orange' },
  { name: '山东省', short: '鲁', topic: '招生与学籍政策', tone: 'indigo' },
  { name: '湖北省', short: '鄂', topic: '升学与资助政策', tone: 'teal' },
]

const currentModel = computed(() => models.value.find((m) => m.id === modelId.value))
const inputPlaceholder = computed(() => mode.value === 'article'
  ? '输入文章主题或写作要求'
  : '输入教育政策问题')

function renderMd(md: string) {
  if (!md) return ''
  return DOMPurify.sanitize(marked.parse(md) as string)
}
async function scrollBottom() { await nextTick(); threadEl.value?.scrollTo({ top: 1e9 }) }
function autoGrow() {
  const ta = taEl.value!
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
}
async function copy(text: string) { await navigator.clipboard.writeText(text) }
function openArticles() { router.push('/articles') }

async function refreshSessions() { sessions.value = await listSessions() }
async function switchSession(id: number) {
  currentId.value = id
  messages.value = await listMessages(id)
  await scrollBottom()
}
async function newSession() {
  const conv = await createSession()
  await refreshSessions()
  await switchSession(conv.id)
}

function stop() { aborter?.abort() }

async function askPolicy(region: PolicyRegion) {
  if (streaming.value) return
  mode.value = 'policy'
  input.value = `请帮我查询${region.name}最新的${region.topic}，并说明适用对象、办理条件、所需材料和官方查询渠道。`
  await nextTick()
  autoGrow()
  await send()
}

async function send() {
  const content = input.value.trim()
  if (!content || streaming.value) return
  if (mode.value === 'article') {
    await writeArticle(content)
    return
  }
  streaming.value = true
  let replyView: WorkspaceMessage | undefined
  try {
    let sessionId = currentId.value
    if (!sessionId) {
      progress.value = '正在创建会话…'
      const conv = await createSession()
      sessionId = conv.id
      currentId.value = conv.id
      await refreshSessions()
    }

    input.value = ''
    autoGrow()
    const localId = Date.now()
    messages.value.push({ id: 0, _tmp: localId, role: 'user', content })
    messages.value.push({
      id: 0, _tmp: localId + 1, role: 'assistant', content: '',
      citations: undefined as MessageItem['citations'],
    })
    // push 后取回响应式代理，保证流式内容逐段触发重渲染。
    const activeReply = messages.value[messages.value.length - 1]
    replyView = activeReply
    await scrollBottom()
    aborter = new AbortController()
    await chatStream(sessionId, { content, model_id: modelId.value }, {
      onDelta: (t) => { activeReply.content += t; scrollBottom() },
      onProgress: (d) => {
        if (d.stage === 'done') { progress.value = ''; if (d.title) refreshSessions() }
        else progress.value = d.detail || d.stage
      },
      onError: (m) => { progress.value = ''; activeReply.content += `\n\n**[错误]** ${m}` },
    }, aborter.signal)
  } catch (e: any) {
    if (e?.name !== 'AbortError' && replyView) replyView.content += '\n\n**[错误]** 连接中断'
  } finally {
    streaming.value = false
    progress.value = ''
    aborter = null
  }
}

async function writeArticle(topic: string) {
  streaming.value = true
  input.value = ''
  autoGrow()
  const localId = Date.now()
  messages.value.push({ id: 0, _tmp: localId, role: 'user', content: `撰写文章：${topic}` })
  messages.value.push({ id: 0, _tmp: localId + 1, role: 'assistant', content: '' })
  const articleReply = messages.value[messages.value.length - 1]
  progress.value = `正在使用 ${currentModel.value?.name || '所选模型'} 撰写文章…`
  await scrollBottom()
  aborter = new AbortController()
  let completed = false
  let streamFailed = false
  try {
    await generateArticleStream(
      { topic, model_id: modelId.value },
      {
        onDelta: (text) => { articleReply.content += text; scrollBottom() },
        onProgress: (data) => {
          if (data.stage === 'done') {
            completed = true
            articleReply.articleId = data.article.id
            progress.value = ''
            ElMessage.success('文章已生成并保存为草稿')
          } else {
            progress.value = data.detail || data.stage
          }
        },
        onError: (message) => {
          streamFailed = true
          progress.value = ''
          articleReply.content += `\n\n**[生成失败]** ${message}`
        },
      },
      aborter.signal,
    )
    if (!completed && !streamFailed) throw new Error('文章流提前结束')
  } catch (error: any) {
    if (error?.name !== 'AbortError' && !streamFailed) {
      articleReply.content += '\n\n**[生成失败]** 连接中断，请稍后重试。'
    }
  } finally {
    streaming.value = false
    progress.value = ''
    aborter = null
  }
}

onMounted(async () => {
  models.value = await listModels()
  sessions.value = await listSessions()
  if (sessions.value.length) await switchSession(sessions.value[0].id)
})
</script>

<style scoped>
.shell { display: flex; height: 100%; }
/* 侧栏 */
.side { width: 230px; background: #171717; color: #ececec; display: flex; flex-direction: column; padding: 12px; gap: 8px; }
.brand { font-weight: 700; font-size: 16px; padding: 4px 6px 10px; }
.new-chat { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 10px;
  border: 1px solid #2f2f2f; background: transparent; color: #ececec; font-size: 14px; cursor: pointer; }
.new-chat:hover { background: #2f2f2f; }
.plus { font-size: 16px; }
.session-list { flex: 1; overflow-y: auto; margin-top: 6px; }
.session-item { padding: 9px 10px; border-radius: 8px; font-size: 13.5px; cursor: pointer; margin-bottom: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #d4d4d4; }
.session-item.on, .session-item:hover { background: #2f2f2f; color: #fff; }
.side-bottom { border-top: 1px solid #2f2f2f; padding-top: 8px; font-size: 13.5px; }
.side-link { padding: 8px 10px; border-radius: 8px; cursor: pointer; }
.side-link:hover { background: #2f2f2f; }
.user { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; }
.logout { color: #f87171; cursor: pointer; font-size: 12.5px; }
/* 主区 */
.main { flex: 1; display: flex; flex-direction: column; background: #fff; min-width: 0; }
.thread { flex: 1; overflow-y: auto; }
.col { max-width: 768px; margin: 0 auto; padding: 28px 20px 10px; }
.empty-state { max-width: 720px; margin: clamp(64px, 14vh, 132px) auto 24px; }
.greet { text-align: center; font-size: 28px; font-weight: 650; color: #262626; }
.greet-sub { margin: 8px 0 24px; text-align: center; color: #737373; font-size: 14px; }
.policy-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.policy-card { --accent: #475569; width: 100%; min-height: 76px; display: flex; align-items: center; gap: 12px;
  border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; background: #fff; color: #262626;
  text-align: left; cursor: pointer; transition: border-color .15s, box-shadow .15s, transform .15s; }
.policy-card:hover { border-color: var(--accent); box-shadow: 0 4px 14px rgba(15,23,42,.08); transform: translateY(-1px); }
.policy-card:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.policy-card:disabled { cursor: wait; opacity: .6; transform: none; }
.policy-mark { width: 38px; height: 38px; flex: 0 0 38px; display: grid; place-items: center; border-radius: 50%;
  color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, white); font-weight: 700; }
.policy-copy { min-width: 0; display: flex; flex: 1; flex-direction: column; gap: 4px; }
.policy-copy strong { font-size: 14px; font-weight: 650; }
.policy-copy small { color: #737373; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.policy-arrow { color: #a3a3a3; flex: 0 0 auto; }
.tone-red { --accent: #b91c1c; }
.tone-blue { --accent: #1d4ed8; }
.tone-green { --accent: #15803d; }
.tone-gold { --accent: #a16207; }
.tone-cyan { --accent: #0e7490; }
.tone-orange { --accent: #c2410c; }
.tone-indigo { --accent: #4338ca; }
.tone-teal { --accent: #0f766e; }
.row { margin-bottom: 26px; }
.row.user { display: flex; justify-content: flex-end; }
.u-bubble { max-width: 70%; background: #f4f4f4; border-radius: 18px; padding: 10px 16px;
  font-size: 15px; line-height: 1.7; white-space: pre-wrap; }
.ai-head { font-size: 12.5px; font-weight: 700; color: #7c3aed; margin-bottom: 6px; }
.ai-content { font-size: 15px; line-height: 1.75; color: #1e293b; }
.cites { font-size: 12.5px; color: #64748b; margin-top: 8px; }
.cites a { color: #2563eb; margin-right: 8px; }
.ai-actions { display: flex; gap: 4px; margin-top: 8px; opacity: 0; transition: opacity .15s; }
.row.ai:hover .ai-actions { opacity: 1; }
.act { border: none; background: transparent; font-size: 15px; cursor: pointer; color: #8e8ea0; padding: 4px 8px; border-radius: 6px; }
.act:hover { background: #f4f4f4; color: #333; }
.act:disabled { cursor: not-allowed; opacity: .5; }
.progress { color: #8e8ea0; font-size: 13px; }
.article-link { display: inline-flex; align-items: center; gap: 6px; margin-top: 12px; border: 1px solid #dbe4dc;
  border-radius: 7px; padding: 8px 10px; background: #f4f8f4; color: #27633b; font-size: 13px; cursor: pointer; }
.article-link:hover { border-color: #8db39a; background: #edf5ef; }
/* 输入区（ChatGPT 式胶囊输入框） */
.composer-zone { padding: 8px 20px 14px; }
.mode-switch { max-width: 768px; min-height: 38px; margin: 0 auto 8px; display: flex; align-items: center; gap: 4px;
  border-bottom: 1px solid #ececec; }
.mode-switch button { height: 36px; display: inline-flex; align-items: center; gap: 6px; border: none;
  border-bottom: 2px solid transparent; padding: 0 13px; background: transparent; color: #737373;
  font: inherit; font-size: 13px; cursor: pointer; }
.mode-switch button:hover:not(:disabled) { color: #262626; background: #f7f7f7; }
.mode-switch button.active { border-bottom-color: #262626; color: #171717; font-weight: 650; }
.mode-switch button:disabled { cursor: not-allowed; color: #b5b5b5; }
.mode-switch button small { font-size: 10px; color: #a3a3a3; }
.custom-wrap { display: inline-flex; }
.composer { max-width: 768px; margin: 0 auto; display: flex; align-items: flex-end; gap: 8px;
  border: 1px solid #d9d9e3; border-radius: 26px; padding: 10px 12px 10px 18px;
  box-shadow: 0 2px 12px rgba(0,0,0,.05); background: #fff; }
.composer:focus-within { border-color: #b3b3c6; }
.composer textarea { flex: 1; border: none; outline: none; resize: none; font-size: 15px;
  line-height: 1.6; max-height: 200px; font-family: inherit; background: transparent; }
.send { width: 34px; height: 34px; border-radius: 50%; border: none; background: #1e1e1e; color: #fff;
  font-size: 17px; cursor: pointer; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.send:disabled { background: #d9d9e3; cursor: not-allowed; }
.send.stop { background: #1e1e1e; }
/* 发送按钮右侧的模型切换入口 */
.model-chip { display: flex; align-items: center; gap: 4px; border: none; background: transparent;
  color: #6b7280; font-size: 13px; cursor: pointer; padding: 8px 8px; border-radius: 10px;
  flex-shrink: 0; align-self: flex-end; margin-bottom: 1px; white-space: nowrap; }
.model-chip:hover { background: #f4f4f4; color: #1e293b; }
.tag { font-size: 11px; color: #b45309; background: #fef3c7; border-radius: 6px; padding: 1px 6px; }
:deep(.el-dropdown-menu__item.picked) { color: #7c3aed; font-weight: 600; background: #f5f3ff; }
.disclaimer { max-width: 768px; margin: 8px auto 0; text-align: center; color: #8e8ea0; font-size: 12px; }
/* Markdown 样式 */
.md :deep(h1), .md :deep(h2), .md :deep(h3) { margin: 14px 0 8px; font-size: 1.06em; }
.md :deep(p) { margin: 8px 0; }
.md :deep(ul), .md :deep(ol) { padding-left: 22px; margin: 8px 0; }
.md :deep(li) { margin: 4px 0; }
.md :deep(code) { background: #f4f4f4; border-radius: 4px; padding: 1px 5px; font-size: 13px; }
.md :deep(pre) { background: #f7f7f8; border-radius: 10px; padding: 12px; overflow-x: auto; }
.md :deep(blockquote) { border-left: 3px solid #d9d9e3; margin: 8px 0; padding: 2px 12px; color: #6b7280; }
.md :deep(strong) { font-weight: 700; }
@media (max-width: 720px) {
  .side { width: 176px; }
  .col { padding-inline: 14px; }
  .empty-state { margin-top: 36px; }
  .policy-grid { grid-template-columns: 1fr; }
  .composer-zone { padding-inline: 12px; }
  .model-chip { max-width: 118px; overflow: hidden; text-overflow: ellipsis; }
}
</style>
