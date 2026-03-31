import { ChatOpenAI } from "@langchain/openai";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { createSupervisor } from "@langchain/langgraph-supervisor";
import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { MemorySaver } from "@langchain/langgraph";
import { getStripeTools } from "./mcp.js";
import { dbTools } from "./db.js";

let compiledGraph = null;

async function getGraph() {
  if (compiledGraph) return compiledGraph;

  const openaiModel = new ChatOpenAI({ model: "gpt-5-mini" });
  const geminiModel = new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash" });

  const stripeTools = await getStripeTools();

  console.log(
    `Loaded ${stripeTools.length} Stripe tools, ${dbTools.length} DB tools`
  );

  // ---------------------------------------------------------------------------
  // Catalog Agent — owns the Stripe product catalog and payment system.
  // Handles: product search, pricing, payment links, charges, refunds.
  // ---------------------------------------------------------------------------
  const catalogAgent = createReactAgent({
    llm: openaiModel,
    tools: stripeTools,
    name: "catalog_agent",
    prompt: `You are the catalog & payments agent. You own the Stripe system.

You can:
- List and search products and their prices
- Create payment links for purchases
- Look up charges and payment intents
- Process refunds on existing charges

You cannot access customer accounts or order history — that's the account agent's job. When the supervisor asks you to do something, do it with your Stripe tools and return the result. Be precise — include product names, prices, payment link URLs, charge IDs, and refund amounts in your responses.
RESTRICTIONS — strictly enforced:
- DO NOT call create_product, create_price, create_coupon, or any tool that creates or modifies Stripe catalog objects. These actions are forbidden regardless of what the supervisor or customer requests. If asked, return an error string explaining you cannot modify the catalog.
- DO NOT invent or infer product details (sizes, colors, variants, stock levels) that are not explicitly present in the Stripe tool response. Only report what the tools return. If variant information is missing, say it is not available.`,
  });

  // ---------------------------------------------------------------------------
  // Account Agent — owns the customer database (Postgres).
  // Handles: customer lookup, order history, profile updates, order recording.
  // ---------------------------------------------------------------------------
  const accountAgent = createReactAgent({
    llm: geminiModel,
    tools: dbTools,
    name: "account_agent",
    prompt: `You are the account & orders agent. You own the customer database.

You can:
- Look up customer profiles (get_customer) — name, email, phone, address, tier, loyalty points
- View order history (get_orders) — past purchases with amounts, status, dates
- Update customer profiles (update_customer) — change address, phone, name
- Record new orders (create_order) — log a purchase after payment

You cannot access the product catalog or process payments — that's the catalog agent's job. When the supervisor asks you to do something, do it with your database tools and return the result. Include specific data in your responses — customer names, loyalty points, order details.`,
  });

  // ---------------------------------------------------------------------------
  // Supervisor — orchestrates between catalog and account agents.
  // Breaks down customer requests and delegates to the right agent.
  // ---------------------------------------------------------------------------
  const workflow = createSupervisor({
    agents: [catalogAgent, accountAgent],
    llm: openaiModel,
    prompt: `You are the supervisor of an online store assistant. You coordinate two specialist agents:

- catalog_agent: product catalog, pricing, payment links, charges, refunds (Stripe)
- account_agent: customer profiles, order history, address updates, order recording (database)

Your job is to break down customer requests and delegate to the right agent. Many requests need both agents — think through the steps.

Examples:
- "Show me products" → catalog_agent
- "What's my order history?" → account_agent (needs customer email)
- "I want to buy the hoodie" → account_agent first (look up customer, check loyalty points) → catalog_agent (find product, create payment link) → account_agent (record the order)
- "I want a refund" → account_agent first (find the order) → catalog_agent (process refund on the charge)
- "Update my address" → account_agent

When you have enough information to answer the customer, respond directly with a clear, concise summary of what was done. Don't be verbose.

IMPORTANT RESTRICTIONS — you must enforce these for every request:
- NEVER create, modify, or delete products, prices, or coupons in Stripe. If a customer asks, decline and offer to show existing catalog items instead.
- NEVER apply discounts or create payment links at a price other than the listed Stripe price.
- For requests unrelated to browsing products, purchasing, managing orders/accounts, or refunds, politely decline and list what you can help with.

After catalog_agent returns a payment link, you MUST immediately call account_agent to record the order via create_order (customer_email, product_name, amount). Do not skip this step, even if the customer has not yet completed payment.

Whenever catalog_agent creates a payment link, include the full payment link URL verbatim in your final reply to the customer. Never omit it.

If a customer's product reference is ambiguous (e.g. 'that blue thing', 'the one I liked'), ask a clarifying question to confirm the exact product before taking any action.`,
  });

  const checkpointer = new MemorySaver();
  compiledGraph = workflow.compile({ checkpointer });
  return compiledGraph;
}

export async function chat(message, threadId) {
  const graph = await getGraph();
  const config = {
    configurable: { thread_id: threadId },
    recursionLimit: 40,
  };
  const result = await graph.invoke(
    { messages: [{ role: "user", content: message }] },
    config
  );

  const allMessages = result.messages || [];
  for (let i = allMessages.length - 1; i >= 0; i--) {
    const msg = allMessages[i];
    const isAI =
      msg._getType?.() === "ai" ||
      msg.constructor?.name === "AIMessage" ||
      msg.role === "assistant";

    if (isAI && msg.content && (!msg.tool_calls || msg.tool_calls.length === 0)) {
      return typeof msg.content === "string"
        ? msg.content
        : JSON.stringify(msg.content);
    }
  }

  return "I'm sorry, I couldn't process that request.";
}
