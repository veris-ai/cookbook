import pg from "pg";
import { tool } from "@langchain/core/tools";
import { z } from "zod";

const pool = new pg.Pool({
  connectionString:
    process.env.DATABASE_URL ||
    "postgresql://postgres:postgres@localhost:5432/sandbox",
});

// ---------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------

const getCustomer = tool(
  async ({ email }) => {
    const result = await pool.query(
      "SELECT * FROM customers WHERE email = $1",
      [email]
    );
    if (result.rows.length === 0) {
      return JSON.stringify({ error: "Customer not found" });
    }
    return JSON.stringify(result.rows[0]);
  },
  {
    name: "get_customer",
    description:
      "Look up a customer profile by email. Returns name, email, phone, address, tier, and loyalty points.",
    schema: z.object({
      email: z.string().describe("The customer's email address"),
    }),
  }
);

const updateCustomer = tool(
  async ({ email, name, phone, address }) => {
    const sets = [];
    const values = [];
    let idx = 1;

    if (name) {
      sets.push(`name = $${idx++}`);
      values.push(name);
    }
    if (phone) {
      sets.push(`phone = $${idx++}`);
      values.push(phone);
    }
    if (address) {
      sets.push(`address = $${idx++}`);
      values.push(address);
    }

    if (sets.length === 0) {
      return JSON.stringify({ error: "No fields to update" });
    }

    values.push(email);
    const result = await pool.query(
      `UPDATE customers SET ${sets.join(", ")} WHERE email = $${idx} RETURNING *`,
      values
    );

    if (result.rows.length === 0) {
      return JSON.stringify({ error: "Customer not found" });
    }
    return JSON.stringify(result.rows[0]);
  },
  {
    name: "update_customer",
    description:
      "Update a customer's profile fields (name, phone, address) by email.",
    schema: z.object({
      email: z.string().describe("The customer's email address"),
      name: z.string().optional().describe("New name"),
      phone: z.string().optional().describe("New phone number"),
      address: z.string().optional().describe("New shipping address"),
    }),
  }
);

const getOrders = tool(
  async ({ email }) => {
    const result = await pool.query(
      "SELECT * FROM orders WHERE customer_email = $1 ORDER BY created_at DESC",
      [email]
    );
    if (result.rows.length === 0) {
      return JSON.stringify({ message: "No orders found for this customer" });
    }
    return JSON.stringify(result.rows);
  },
  {
    name: "get_orders",
    description:
      "Query a customer's order history by email. Returns all orders with product, amount, status, and date.",
    schema: z.object({
      email: z.string().describe("The customer's email address"),
    }),
  }
);

const createOrder = tool(
  async ({ customer_email, product_name, amount, status }) => {
    const result = await pool.query(
      `INSERT INTO orders (customer_email, product_name, amount, status, created_at)
       VALUES ($1, $2, $3, $4, NOW()) RETURNING *`,
      [customer_email, product_name, amount, status || "pending"]
    );
    return JSON.stringify(result.rows[0]);
  },
  {
    name: "create_order",
    description:
      "Record a new order in the database after a purchase is made.",
    schema: z.object({
      customer_email: z.string().describe("The customer's email address"),
      product_name: z.string().describe("Name of the product purchased"),
      amount: z.number().describe("Order amount in dollars"),
      status: z
        .string()
        .optional()
        .describe("Order status (default: pending)"),
    }),
  }
);

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export const dbTools = [getCustomer, updateCustomer, getOrders, createOrder];

export async function closeDb() {
  await pool.end();
}
