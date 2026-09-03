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
      path: "/reviews",
      name: "reviews",
      component: () => import("@/pages/Review.vue"),
    },
    {
      path: "/audit",
      name: "audit",
      component: () => import("@/pages/AuditLog.vue"),
    },
    {
      path: "/templates",
      name: "templates",
      component: () => import("@/pages/Templates.vue"),
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("@/pages/Settings.vue"),
    },
  ],
});

export default router;