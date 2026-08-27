<template>
  <div>
    <el-carousel v-if="images.length" height="400px" arrow="always">
      <el-carousel-item v-for="(img, i) in images" :key="i">
        <div class="img-wrap">
          <img :src="img.url" :alt="img.label" />
        </div>
      </el-carousel-item>
    </el-carousel>
    <el-empty v-else description="暂无截图" />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ images: { url: string; label: string }[] }>();

// 后端返回本地路径时，转为可访问的代理地址
const images = computed(() =>
  props.images.filter((i) => i.url).map((i) => ({ ...i }))
);
</script>

<style scoped>
.img-wrap {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
}
.img-wrap img {
  max-height: 100%;
  max-width: 100%;
  object-fit: contain;
}
</style>