# NovaStore - E-Commerce Storefront with Order API Forwarding

A clean, responsive, modern e-commerce storefront crafted in vanilla HTML, CSS, and JavaScript. It features an interactive shopping cart and forwards full order payloads to any external REST / Webhook API endpoint you configure.

---

## 🚀 Getting Started

1. **Start the local server:**
   ```bash
   python -m http.server 3000
   ```
2. **Open your browser:**
   Go to [http://localhost:3000](http://localhost:3000).

---

## ⚙️ How to Configure the Order API Endpoint

Open [config.js](file:///c:/Users/neil-/Projects/Ecom/config.js) in your editor:

```javascript
const CONFIG = {
  // Store settings
  storeName: "NovaStore",
  currency: "$",
  currencyCode: "USD",
  taxRate: 0.08,
  shippingFee: 15.00,
  freeShippingThreshold: 100.00,

  // Change this to your destination order webhook or external API URL:
  ORDER_API_ENDPOINT: "https://your-api.com/api/orders",

  // Custom HTTP headers (API key, bearer token, etc.)
  API_HEADERS: {
    "Content-Type": "application/json",
    // "Authorization": "Bearer YOUR_SECRET_TOKEN"
  },

  ALLOW_OFFLINE_SIMULATION: true,
};
```

You can also test endpoints directly in the browser by clicking the **"Order API Webhook"** badge in the top right navigation bar.

---

## 📦 Order JSON Payload Structure

When a customer submits the checkout form, an `HTTP POST` request is sent with the following JSON schema:

```json
{
  "orderId": "ORD-M3K9X1-842",
  "timestamp": "2026-10-15T14:05:00.000Z",
  "storeName": "NovaStore",
  "customer": {
    "fullName": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+1 (555) 234-5678",
    "address": {
      "line1": "742 Evergreen Terrace",
      "line2": "",
      "city": "Springfield",
      "state": "OR",
      "postalCode": "97477",
      "country": "United States"
    },
    "paymentMethod": "Credit Card",
    "notes": "Please leave at front door."
  },
  "pricing": {
    "currency": "USD",
    "subtotal": 189.99,
    "shippingFee": 0.00,
    "tax": 15.20,
    "total": 205.19
  },
  "items": [
    {
      "productId": "prod-1",
      "name": "Minimalist Ergonomic Chair",
      "category": "Furniture",
      "unitPrice": 189.99,
      "quantity": 1,
      "lineTotal": 189.99
    }
  ]
}
```

---

## 🛍️ How to Update Products

Product records are maintained in [config.js](file:///c:/Users/neil-/Projects/Ecom/config.js) under `INITIAL_PRODUCTS`. Simply add, edit, or replace the list with your own product catalog whenever you are ready:

```javascript
{
  id: "prod-x",
  name: "Your Product Name",
  category: "Your Category",
  price: 99.99,
  originalPrice: 129.99,
  rating: 4.8,
  reviewsCount: 42,
  badge: "Featured",
  image: "https://your-image-url.jpg",
  description: "Product details and description."
}
```
