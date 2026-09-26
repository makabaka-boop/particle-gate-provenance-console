<script setup>
import { computed } from 'vue'

const props = defineProps({
  gate: { type: Object, default: null },
  hitIds: { type: Array, required: true },
})

const preview = computed(() => {
  const ids = props.hitIds
  if (ids.length <= 40) return ids.join(', ')
  return ids.slice(0, 40).join(', ') + ` … (共 ${ids.length} 个)`
})
</script>

<template>
  <div class="panel" data-testid="gate-detail">
    <h2>选中门详情</h2>
    <div class="body">
      <p v-if="!gate" class="empty-hint">在右侧门控表中点击任一门, 散点将高亮该门命中的颗粒及其输入门。</p>
      <div v-else class="detail">
        <p>门 id: <b data-testid="detail-id">{{ gate.id }}</b></p>
        <p v-if="gate.type === 'polygon'">
          类型: <b>凸多边形</b>, {{ gate.vertices.length }} 个顶点<br />
          顶点(按环向):
        </p>
        <ol v-if="gate.type === 'polygon'" class="vector-cell">
          <li v-for="(v, i) in gate.vertices" :key="i">({{ v[0] }}, {{ v[1] }})</li>
        </ol>
        <p v-else>
          类型: <b>组合门</b><br />
          运算: <b>{{ gate.op }}</b><br />
          左输入门: <b>{{ gate.left }}</b><br />
          右输入门: <b>{{ gate.right }}</b><br />
          <span class="vector-cell">
            AND=交集 · OR=并集 · DIFF=左集减右集
          </span>
        </p>
        <p>命中数量: <b data-testid="detail-count">{{ gate.count }}</b></p>
        <p>命中点 id(排序):</p>
        <p class="ids-line" data-testid="detail-ids">{{ preview || '(空集)' }}</p>
      </div>
    </div>
  </div>
</template>
