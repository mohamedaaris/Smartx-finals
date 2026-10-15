/**
 * Lightweight Order Receiver Server
 * 
 * Run this on Laptop 2 (or any receiver machine) on the same Wi-Fi.
 * It accepts orders from the storefront via GET or POST on any common route.
 * 
 * Usage:
 *   node receiver_server.js
 */

const http = require("http");
const os = require("os");
const url = require("url");

const PORT = process.env.PORT || 5000;
const HOST = "0.0.0.0"; // Listens on all network interfaces

// In-memory order log
const orderHistory = [];

// Helper to get local Wi-Fi IP address
function getLocalIp() {
  const nets = os.networkInterfaces();
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === "IPv4" && !net.internal) {
        return net.address;
      }
    }
  }
  return "localhost";
}

const server = http.createServer((req, res) => {
  // Always log every incoming request
  console.log(`➡️  [${new Date().toLocaleTimeString()}] ${req.method} ${req.url}`);

  // 1. Enable Full Permissive CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "*");

  // Handle preflight OPTIONS request
  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // Parse path
  const parsedUrl = url.parse(req.url, true);
  let pathname = (parsedUrl.pathname || "/").toLowerCase();
  if (pathname.length > 1 && pathname.endsWith("/")) {
    pathname = pathname.slice(0, -1);
  }

  // 2. Browser Dashboard (GET / or GET /orders)
  if (req.method === "GET" && (pathname === "/" || pathname === "/orders")) {
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Order Receiver Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          body { font-family: system-ui, sans-serif; background: #0b0f19; color: #f1f5f9; padding: 2rem; max-width: 900px; margin: 0 auto; }
          h1 { color: #818cf8; margin-bottom: 0.2rem; }
          .badge { background: #10b98120; border: 1px solid #10b981; color: #34d399; padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 700; }
          .card { background: #151d30; border: 1px solid #283454; border-radius: 10px; padding: 1.25rem; margin-top: 1.25rem; }
          pre { background: #090c14; padding: 1rem; border-radius: 6px; overflow-x: auto; color: #38bdf8; font-size: 0.85rem; }
          .btn-refresh { background: #6366f1; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }
        </style>
      </head>
      <body>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h1>📡 Simulation Order Receiver</h1>
            <p style="color: #94a3b8; font-size: 0.9rem;">Listening for orders from Wi-Fi devices | <span class="badge">LIVE</span></p>
          </div>
          <button class="btn-refresh" onclick="window.location.reload()">Refresh Orders (${orderHistory.length})</button>
        </div>

        ${orderHistory.length === 0 ? `
          <div class="card" style="text-align: center; color: #94a3b8; padding: 3rem;">
            No orders received yet. Place an order on the e-commerce store to see it arrive here in real time!
          </div>
        ` : orderHistory.slice().reverse().map((ord, idx) => `
          <div class="card">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
              <strong style="color: #c7d2fe; font-size: 1.1rem;">Order #${ord.orderid || 'N/A'}</strong>
              <span style="color: #94a3b8; font-size: 0.85rem;">${ord.time || ''}</span>
            </div>
            <p style="margin: 0.25rem 0; font-size: 0.95rem;">Product Name: <strong style="color: #818cf8;">${ord.productname || ord.product || 'N/A'}</strong></p>
            <details style="margin-top: 0.75rem;">
              <summary style="cursor: pointer; color: #818cf8; font-size: 0.85rem;">View Exact JSON Payload</summary>
              <pre>${JSON.stringify(ord, null, 2)}</pre>
            </details>
          </div>
        `).join('')}
      </body>
      </html>
    `);
    return;
  }

  // 3. GET /api/orders (or any other GET) - Returns the actual received order information!
  if (req.method === "GET") {
    const latestOrder = orderHistory.length > 0 ? orderHistory[orderHistory.length - 1] : null;

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: "online",
      totalOrders: orderHistory.length,
      latestOrder: latestOrder,
      orders: orderHistory
    }, null, 2));
    return;
  }

  // 4. POST / PUT handler: Accept orders from any URL
  if (req.method === "POST" || req.method === "PUT") {
    let body = "";

    req.on("data", chunk => {
      body += chunk.toString();
    });

    req.on("end", () => {
      try {
        let payload = {};
        if (body.trim().length > 0) {
          payload = JSON.parse(body);
        }

        // Handle ping / test connection button
        if (payload.ping || payload.test) {
          console.log("⚡ Ping connection test verified successfully!");
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ success: true, message: "Ping connection verified successfully!" }));
          return;
        }

        // Support exact requested structure: orderid, productname, time
        const orderid = payload.orderid || payload.orderId || ("ORD-" + Date.now().toString(36).toUpperCase());
        const productname = payload.productname || payload.product || (payload.items ? payload.items.map(i => i.name).join(", ") : "Unspecified Product");
        const time = payload.time || payload.timestamp || new Date().toISOString();

        const cleanOrder = {
          orderid: orderid,
          productname: productname,
          time: time
        };

        console.log(`\n========================================`);
        console.log(`📥 NEW ORDER RECEIVED [${new Date().toLocaleTimeString()}]:`);
        console.log(`   orderid:     ${cleanOrder.orderid}`);
        console.log(`   productname: ${cleanOrder.productname}`);
        console.log(`   time:        ${cleanOrder.time}`);
        console.log(`========================================\n`);

        orderHistory.push(cleanOrder);

        // Success response sent back to the customer's browser
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({
          success: true,
          status: "Order received",
          orderid: cleanOrder.orderid,
          productname: cleanOrder.productname,
          time: cleanOrder.time
        }));
      } catch (err) {
        console.error("❌ Failed to parse request JSON:", err.message, "Raw Body was:", body);
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid JSON payload", details: err.message }));
      }
    });
    return;
  }

  // Fallback
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ status: "OK" }));
});

server.listen(PORT, HOST, () => {
  const localIp = getLocalIp();
  console.log(`\n======================================================`);
  console.log(`🚀 Simulation Order Receiver is LIVE!`);
  console.log(`------------------------------------------------------`);
  console.log(`On this machine (Laptop 2):`);
  console.log(`👉 View Dashboard:  http://localhost:${PORT}/orders`);
  console.log(`\nFrom the other machine (Laptop 1 Storefront):`);
  console.log(`👉 Set Endpoint to: http://${localIp}:${PORT}/api/orders`);
  console.log(`======================================================\n`);
});
