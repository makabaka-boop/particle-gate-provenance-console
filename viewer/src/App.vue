<script setup>
import { computed, ref, shallowRef } from 'vue'
import { evaluateGates } from './api.js'
import { SAMPLE_POINTS, SAMPLE_GATES } from './sample.js'
import ScatterPlot from './components/ScatterPlot.vue'
import GateTable from './components/GateTable.vue'
import GateDetail from './components/GateDetail.vue'

const pointsText = ref(JSON.stringify(SAMPLE_POINTS, null, 2))
const gatesText = ref(JSON.stringify(SAMPLE_GATES, null, 2))

// 每次成功响应分配一个前端侧递增 id。散点图与门控表都渲染同一个
// result 对象, DOM 上同时挂 data-response-id, 供浏览器流程核对
// "散点和门控表共享同一响应"。
let responseSeq = 0
const result = shallowRef(null)
const responseId = ref(0)
const selectedId = ref(null)
const loading = ref(false)
const error = ref('')

// 竞态防护:
//  1) runSeq 单调递增, 响应回来时序号不对则丢弃(旧请求不得覆盖新编辑);
//  2) 编辑后 dirty=true, 在途请求一律 abort;
//  3) 已有结果标 stale, 直到下次成功计算。
let runSeq = 0
let inFlight = null
const dirty = ref(false)
const stale = computed(() => dirty.value && result.value !== null)

function markDirty() {
  dirty.value = true
  if (inFlight) {
    inFlight.abort()
    inFlight = null
  }
}

async function runEvaluate() {
  error.value = ''
  let payload
  try {
    const points = JSON.parse(pointsText.value)
    const gates = JSON.parse(gatesText.value)
    payload = { points, gates }
  } catch (err) {
    error.value = `JSON 解析失败: ${err.message}`
    return
  }

  const seq = ++runSeq
  const controller = new AbortController()
  inFlight = controller
  loading.value = true
  try {
    const data = await evaluateGates(payload, controller.signal)
    if (seq !== runSeq) return // 已被新的编辑/请求作废
    result.value = data
    responseId.value = ++responseSeq
    // 若上一次选中的门仍存在则保留, 否则清空。
    if (selectedId.value && !data.gates.some((g) => g.id === selectedId.value)) {
      selectedId.value = null
    }
    dirty.value = false
  } catch (err) {
    if (err.name === 'AbortError') return
    if (seq !== runSeq) return
    error.value = err.message
  } finally {
    if (seq === runSeq) {
      loading.value = false
      inFlight = null
    }
  }
}

function loadSample() {
  pointsText.value = JSON.stringify(SAMPLE_POINTS, null, 2)
  gatesText.value = JSON.stringify(SAMPLE_GATES, null, 2)
  markDirty()
  error.value = ''
}

const gates = computed(() => result.value?.gates ?? [])
const points = computed(() => result.value?.points ?? [])
const vectorsById = computed(() => {
  const map = {}
  for (const v of result.value?.vectors ?? []) map[v.id] = v.hits
  return map
})

// 组合门的两个直接输入门 id(多边形门为空)。
const inputsOf = (g) =>
  g && g.type === 'combine' ? [g.left, g.right] : []

const selectedGate = computed(
  () => gates.value.find((g) => g.id === selectedId.value) || null,
)

const selectedHitIds = computed(
  () => new Set(selectedGate.value?.hitIds ?? []),
)

// 直接输入门及其命中集合, 用于散点与门控表高亮。
const inputGateIds = computed(() => {
  const g = selectedGate.value
  if (!g || g.type !== 'combine') return []
  return [g.left, g.right].filter(
    (id, idx, arr) => arr.indexOf(id) === idx && gates.value.some((x) => x.id === id),
  )
})
const inputHitIds = computed(() => {
  const s = new Set()
  for (const id of inputGateIds.value) {
    const gate = gates.value.find((x) => x.id === id)
    for (const hid of gate.hitIds) s.add(hid)
  }
  // 选中门自己的命中不算"仅输入门"颜色: ScatterPlot 里优先判选中。
  return s
})

const selectedHitList = computed(() => selectedGate.value?.hitIds ?? [])

const statusText = computed(() => {
  if (loading.value) return '计算中…'
  if (!result.value) return '尚未计算'
  return `${result.value.points.length} 个点 · ${result.value.gates.length} 个门 · 响应 #${responseId.value}`
})
</script>

<template>
  <header class="topbar">
    <h1>颗粒检测仪 · 多级门控散点编辑</h1>
    <div class="actions">
      <button data-testid="run" :disabled="loading" @click="runEvaluate">
        {{ loading ? '计算中…' : '计算门控' }}
      </button>
      <button class="ghost" data-testid="sample" @click="loadSample">载入示例</button>
    </div>
    <span
      class="status"
      :class="{ stale }"
      data-testid="status"
      :data-response-id="responseId"
    >
      {{ statusText }}<template v-if="stale"> · 输入已修改, 当前结果为旧响应</template>
    </span>
  </header>

  <div class="layout">
    <section class="panel" data-testid="editor">
      <h2>输入编辑(至多 5000 点 / 20 门)</h2>
      <div class="body">
        <label class="field">
          points — [{ id, size, intensity }], 坐标 0~1000 整数
          <textarea
            v-model="pointsText"
            class="json-input"
            data-testid="points-input"
            @input="markDirty"
          ></textarea>
        </label>
        <label class="field">
          gates — polygon(3~12 顶点凸多边形)或 combine(AND/OR/DIFF, 仅引用更早门)
          <textarea
            v-model="gatesText"
            class="json-input"
            rows="10"
            data-testid="gates-input"
            @input="markDirty"
          ></textarea>
        </label>
        <div v-if="error" class="error-box" data-testid="error">{{ error }}</div>
        <p class="meta-line" style="margin-top: 12px">
          边界点算命中; 未知字段 / 未知或逆向引用 / 重复 id / 非凸或零面积多边形
          将被服务端整次拒绝(422)。
        </p>
      </div>
    </section>

    <ScatterPlot
      :points="points"
      :gates="gates"
      :vectors-by-id="vectorsById"
      :selected-id="selectedId"
      :selected-hit-ids="selectedHitIds"
      :input-hit-ids="inputHitIds"
      :input-gate-ids="inputGateIds"
      :response-id="responseId"
    />

    <div style="display: flex; flex-direction: column; gap: 12px; min-height: 0;">
      <GateTable
        :gates="gates"
        :selected-id="selectedId"
        :input-gate-ids="inputGateIds"
        :response-id="responseId"
        @select="selectedId = $event"
      />
      <GateDetail :gate="selectedGate" :hit-ids="selectedHitList" />
    </div>
  </div>
</template>
