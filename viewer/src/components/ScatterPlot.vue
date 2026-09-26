<script setup>
import { computed } from 'vue'

const props = defineProps({
  points: { type: Array, required: true },
  gates: { type: Array, required: true },
  vectorsById: { type: Object, required: true },
  selectedId: { type: String, default: null },
  selectedHitIds: { type: Set, required: true },
  inputHitIds: { type: Set, required: true },
  inputGateIds: { type: Array, required: true },
  responseId: { type: Number, default: 0 },
})

const W = 720
const H = 720
const M = 46
const PLOT = W - M * 2

function x(size) {
  return M + (size / 1000) * PLOT
}
function y(intensity) {
  return H - M - (intensity / 1000) * PLOT
}

function pointClass(p) {
  if (props.selectedId && props.selectedHitIds.has(p.id)) return 'hit-selected'
  if (props.selectedId && props.inputHitIds.has(p.id)) return 'hit-input'
  return 'dim'
}

function vectorText(p) {
  const vec = props.vectorsById[p.id]
  return vec ? vec.join('') : ''
}

const selectedGate = computed(
  () => props.gates.find((g) => g.id === props.selectedId) || null,
)
const inputGates = computed(() =>
  props.gates.filter((g) => props.inputGateIds.includes(g.id)),
)

function polygonPoints(vertices) {
  return vertices.map(([s, i]) => `${x(s)},${y(i)}`).join(' ')
}

const ticks = [0, 250, 500, 750, 1000]
</script>

<template>
  <div class="panel" data-testid="scatter" :data-response-id="responseId">
    <h2>散点 (size → x, intensity → y)</h2>
    <div class="body" style="padding: 8px">
      <svg
        :viewBox="`0 0 ${W} ${H}`"
        width="100%"
        role="img"
        aria-label="颗粒散点图"
        data-testid="scatter-svg"
      >
        <rect
          :x="M"
          :y="M"
          :width="PLOT"
          :height="PLOT"
          fill="#0c111d"
          stroke="#2b3650"
        />
        <g v-for="t in ticks" :key="'gx' + t">
          <line
            :x1="x(t)"
            :y1="M"
            :x2="x(t)"
            :y2="H - M"
            stroke="#1c2740"
            stroke-width="1"
          />
          <text
            :x="x(t)"
            :y="H - M + 18"
            fill="#8a97b2"
            font-size="11"
            text-anchor="middle"
          >
            {{ t }}
          </text>
        </g>
        <g v-for="t in ticks" :key="'gy' + t">
          <line
            :x1="M"
            :y1="y(t)"
            :x2="W - M"
            :y2="y(t)"
            stroke="#1c2740"
            stroke-width="1"
          />
          <text :x="M - 8" :y="y(t) + 4" fill="#8a97b2" font-size="11" text-anchor="end">
            {{ t }}
          </text>
        </g>
        <text :x="W / 2" :y="H - 6" fill="#8a97b2" font-size="12" text-anchor="middle">
          size
        </text>
        <text
          :x="14"
          :y="H / 2"
          fill="#8a97b2"
          font-size="12"
          text-anchor="middle"
          :transform="`rotate(-90 14 ${H / 2})`"
        >
          intensity
        </text>

        <!-- 输入门多边形(绿) 先画, 选中门多边形(金) 后画 -->
        <polygon
          v-for="g in inputGates.filter((g) => g.type === 'polygon')"
          :key="'poly-in-' + g.id"
          :points="polygonPoints(g.vertices)"
          fill="rgba(76,201,164,0.08)"
          stroke="#4cc9a4"
          stroke-width="1.5"
          stroke-dasharray="6 4"
        />
        <polygon
          v-if="selectedGate && selectedGate.type === 'polygon'"
          :key="'poly-sel'"
          :points="polygonPoints(selectedGate.vertices)"
          fill="rgba(255,209,102,0.14)"
          stroke="#ffd166"
          stroke-width="2.5"
        />
        <text
          v-if="selectedGate && selectedGate.type === 'polygon'"
          :x="x(selectedGate.vertices[0][0])"
          :y="y(selectedGate.vertices[0][1]) - 8"
          fill="#ffd166"
          font-size="12"
        >
          {{ selectedGate.id }}
        </text>

        <g data-testid="points-layer">
          <circle
            v-for="p in points"
            :key="p.id"
            :cx="x(p.size)"
            :cy="y(p.intensity)"
            :r="4"
            :class="['pt', pointClass(p)]"
            :data-point-id="p.id"
            :data-hit-vector="vectorText(p)"
          >
            <title>id={{ p.id }} ({{ p.size }}, {{ p.intensity }})
命中向量: {{ vectorText(p) || '(无门)' }}</title>
          </circle>
        </g>
      </svg>
    </div>
    <div class="legend">
      <span><i class="swatch" style="background: #ffd166"></i>选中门命中</span>
      <span><i class="swatch" style="background: #4cc9a4"></i>输入门命中(未被选中门命中)</span>
      <span><i class="swatch" style="background: #41506f"></i>未命中选中门</span>
    </div>
  </div>
</template>

<style scoped>
.pt {
  stroke: rgba(0, 0, 0, 0.35);
  stroke-width: 0.5;
}
.pt.hit-selected {
  fill: #ffd166;
}
.pt.hit-input {
  fill: #4cc9a4;
}
.pt.dim {
  fill: #41506f;
}
</style>
