import { MultiServerMCPClient } from "@langchain/mcp-adapters";

let client = null;

async function getClient() {
  if (!client) {
    client = new MultiServerMCPClient({
      mcpServers: {
        stripe: {
          url: "https://mcp.stripe.com",
          headers: {
            Authorization: `Bearer ${process.env.STRIPE_SECRET_KEY}`,
          },
        },
      },
    });
  }
  return client;
}

export async function getStripeTools() {
  const mcpClient = await getClient();
  return mcpClient.getTools();
}

export async function closeMCP() {
  if (client) {
    await client.close();
    client = null;
  }
}
