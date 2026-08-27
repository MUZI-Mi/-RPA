import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "instruction",
      component: () => import("@/pages/Instruction.vue"),
    },
    {
      path: "/tasks",
      name: "tasks",
      component: () => import("@/pages/Tasks.vue"),
    },
    {
      path: "/report/:id",
      name: "report",
      component: () => import("@/pages/Report.vue"),
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("@/pages/Settings.vue"),
    },
  ],
});

export default router;