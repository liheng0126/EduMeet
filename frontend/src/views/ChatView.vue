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
          <div v-if="!messages.length" class="greet">有什么可以帮你？</div>
          <template v-for="m in messages" :key="m.id ?? m._tmp">
            <!-- 用户：右对齐灰气泡 -->
            <div v-if="m.role === 'user'" class="row user">
              <div class="u-bubble">{{ m.content }}</div>
            </div>
            <!-- AI：全宽无气泡 Markdown -->
            <div v-else class="row ai">
              <div class="ai-head">EduMeet</div>
              <div class="ai-content md" v-html="renderMd(m.content)"></div>
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
        <div class="composer">
          <textarea ref="taEl" v-model="input" rows="1" placeholder="有问题，随便问"
                    @keydown.enter.exact.prevent="send" @input="autoGrow"></textarea>
          <button v-if="streaming" class="send stop" title="停止" @click="stop">■</button>
          <button v-else class="send" :disabled="!input.trim() || !currentId" title="发送" @click="send">↑</button>
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
import { marked } from 'marked'
import { chatStream, createSession, listMessages, listModels, listSessions, type Conversation, type MessageItem, type ModelInfo } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const sessions = ref<Conversation[]>([])
const currentId = ref<number | null>(null)
const messages = ref<(MessageItem & { _tmp?: number })[]>([])
const models = ref<ModelInfo[]>([])
const modelId = ref('deepseek-chat') // 默认模型：DeepSeek
const input = ref('')
const streaming = ref(false)
const progress = ref('')
const threadEl = ref<HTMLElement>()
const taEl = ref<HTMLTextAreaElement>()
let aborter: AbortController | null = null

const currentModel = computed(() => models.value.find((m) => m.id === modelId.value))

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

async function send() {
  const content = input.value.trim()
  if (!content || !currentId.value || streaming.value) return
  input.value = ''
  autoGrow()
  streaming.value = true
  const localId = Date.now()
  messages.value.push({ id: 0, _tmp: localId, role: 'user', content })
  const reply = { id: 0, _tmp: localId + 1, role: 'assistant', content: '', citations: undefined as MessageItem['citations'] }
  messages.value.push(reply)
  // 关键：push 后取回响应式代理，直接改原始对象 Vue 不会触发重渲染（导致流式内容最后一次性出现）
  const replyView = messages.value[messages.value.length - 1]
  await scrollBottom()
  aborter = new AbortController()
  try {
    await chatStream(currentId.value, { content, model_id: modelId.value }, {
      onDelta: (t) => { replyView.content += t; scrollBottom() },
      onProgress: (d) => {
        if (d.stage === 'done') { progress.value = ''; if (d.title) refreshSessions() }
        else progress.value = d.detail || d.stage
      },
      onError: (m) => { progress.value = ''; replyView.content += `\n\n**[错误]** ${m}` },
    }, aborter.signal)
  } catch (e: any) {
    if (e?.name !== 'AbortError') replyView.content += '\n\n**[错误]** 连接中断'
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
.greet { text-align: center; font-size: 30px; font-weight: 600; color: #8e8ea0; margin-top: 32vh; }
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
/* 输入区（ChatGPT 式胶囊输入框） */
.composer-zone { padding: 8px 20px 14px; }
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
</style>
