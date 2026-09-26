<script setup>
defineProps({
  gates: { type: Array, required: true },
  selectedId: { type: String, default: null },
  inputGateIds: { type: Array, required: true },
  responseId: { type: Number, default: 0 },
})

const emit = defineEmits(['select'])
</script>

<template>
  <div class="panel" data-testid="gate-table" :data-response-id="responseId">
    <h2>门控表(按门顺序, 点击行选中)</h2>
    <div class="body" style="padding: 0">
      <table class="gate-table">
        <thead>
          <tr>
            <th>#</th>
            <th>id</th>
            <th>类型</th>
            <th>定义</th>
            <th>命中数</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(g, i) in gates"
            :key="g.id"
            class="gate-row"
            :class="{
              selected: g.id === selectedId,
              'input-row': inputGateIds.includes(g.id),
            }"
            :data-gate-id="g.id"
            :data-gate-index="i"
            :data-count="g.count"
            @click="emit('select', g.id)"
          >
            <td>{{ i }}</td>
            <td>{{ g.id }}</td>
            <td>
              <span class="tag" :class="g.type">
                {{ g.type === 'polygon' ? '多边形' : g.op }}
              </span>
            </td>
            <td class="vector-cell">
              <template v-if="g.type === 'polygon'">{{ g.vertices.length }} 顶点</template>
              <template v-else>{{ g.left }} · {{ g.right }}</template>
            </td>
            <td data-testid="gate-count">{{ g.count }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!gates.length" class="empty-hint">暂无门</p>
    </div>
  </div>
</template>
