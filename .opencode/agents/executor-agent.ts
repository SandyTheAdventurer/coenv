import { Agent } from "@opencode-ai/plugin"

export const ExecutorAgent: Agent = {
  name: "executor",
  description: "Handles general tasks",

  async run(ctx) {
    return `Executing task: ${ctx.input}`
  }
}

