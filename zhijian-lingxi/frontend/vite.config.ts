import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8710",
        changeOrigin: true,
      },
    },
  },
  // Tauri 需要固定的资源路径
  clearScreen: false,
  build: {
    // 输出到项目根 dist，供 tauri.conf.json 的 frontendDist 引用
    outDir: "../dist",
    emptyOutDir: true,
    target: "esnext",
    minify: "esbuild",
    sourcemap: false,
  },
});