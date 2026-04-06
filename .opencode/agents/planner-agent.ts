import { Agent } from "@opencode-ai/plugin"

export const PlannerAgent: Agent = {
  name: "planner",
  description: "Decides which agent to call",

  async run(ctx) {
    const input = ctx.input

    if (input.includes("remember")) {
      return ctx.call("memory-agent", input)
    }

    if (input.includes("search")) {
      return ctx.call("web-agent", input)
    }

    return ctx.call("executor-agent", input)
  }
}
