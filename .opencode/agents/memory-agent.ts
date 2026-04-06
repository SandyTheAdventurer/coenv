import { Agent } from "@opencode-ai/plugin"

export const MemoryAgent: Agent = {
  name: "memory",
  description: "Handles memory storage and retrieval",

  async run(ctx) {
    const input = ctx.input

    if (input.includes("remember")) {
      return "Saved to memory"
    }

    if (input.includes("recall")) {
      return "Here is your memory"
    }

    return null
  }
}
