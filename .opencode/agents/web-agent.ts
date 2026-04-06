import { Agent } from "@opencode-ai/plugin"

export const WebAgent: Agent = {
  name: "web",
  description: "Fetches web data",

  async run(ctx) {
    return `Searching web for: ${ctx.input}`
  }
}
