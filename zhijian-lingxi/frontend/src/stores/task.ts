import { defineStore } from "pinia";
import { ref } from "vue";
import type { Task } from "@/types";
import * as api from "@/api";

export const useTaskStore = defineStore("task", () => {
  const tasks = ref<Task[]>([]);
  const loading = ref(false);

  async function fetchTasks() {
    loading.value = true;
    try {
      tasks.value = await api.getTasks();
    } finally {
      loading.value = false;
    }
  }

  async function addTask(name: string, config: any) {
    await api.createTask(name, config);
    await fetchTasks();
  }

  async function removeTask(id: string) {
    await api.deleteTask(id);
    await fetchTasks();
  }

  async function run(id: string) {
    await api.runTask(id);
  }

  return { tasks, loading, fetchTasks, addTask, removeTask, run };
});