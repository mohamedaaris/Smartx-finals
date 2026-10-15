/**
 * NovaStore E-Commerce Core Logic
 * Handles state, product rendering, cart management, modal popups,
 * and external API order forwarding with fallback handling.
 */

// Global State
let cart = [];
let activeCategory = "All";
let searchQuery = "";

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  loadSavedCart();
  setupEventListeners();
  renderCategories();
  renderProducts();
  updateCartUI();
  updateEndpointStatusBadge();
});

// Load cart from LocalStorage
function loadSavedCart() {
  try {
    const saved = localStorage.getItem("novastore_cart");
    if (saved) {
      cart = JSON.parse(saved);
    }
  } catch (err) {
    console.error("Failed to load cart from storage", err);
    cart = [];
  }
}

// Save cart to LocalStorage
function saveCart() {
  try {
    localStorage.setItem("novastore_cart", JSON.stringify(cart));
  } catch (err) {
    console.error("Failed to save cart", err);
  }
}

// Category extraction & chip rendering
function renderCategories() {
  const container = document.getElementById("categoryChips");
  if (!container) return;

  const categories = ["All", ...new Set(INITIAL_PRODUCTS.map(p => p.category))];
  
  container.innerHTML = categories.map(cat => `
    <button class="chip-btn ${cat === activeCategory ? 'active' : ''}" data-category="${cat}">
      ${cat}
    </button>
  `).join("");

  container.querySelectorAll(".chip-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      activeCategory = btn.dataset.category;
      container.querySelectorAll(".chip-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderProducts();
    });
  });
}

// Render product catalog
function renderProducts() {
  const grid = document.getElementById("productsGrid");
  if (!grid) return;

  const filtered = INITIAL_PRODUCTS.filter(product => {
    const matchesCategory = activeCategory === "All" || product.category === activeCategory;
    const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          product.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; color: var(--text-secondary);">
        <p style="font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem;">No products found</p>
        <p style="font-size: 0.9rem;">Try adjusting your search query or category filter.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(item => `
    <article class="product-card" id="card-${item.id}">
      <div class="product-thumb-wrap">
        <img class="product-thumb" src="${item.image}" alt="${item.name}" loading="lazy" />
        ${item.badge ? `<span class="product-badge">${item.badge}</span>` : ''}
      </div>
      <div class="product-content">
        <span class="product-category">${item.category}</span>
        <h3 class="product-title">${item.name}</h3>
        <p class="product-desc">${item.description}</p>
        <div class="product-meta">
          <div class="product-price-box">
            <span class="product-price">${CONFIG.currency}${item.price.toFixed(2)}</span>
            ${item.originalPrice ? `<span class="product-original-price">${CONFIG.currency}${item.originalPrice.toFixed(2)}</span>` : ''}
          </div>
          <div class="product-rating">
            <span>★</span> ${item.rating} <span style="color: var(--text-muted); font-size: 0.8rem">(${item.reviewsCount})</span>
          </div>
        </div>
        <div class="product-actions">
          <button class="btn-add-cart" onclick="addToCart('${item.id}')">
            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
            Add to Cart
          </button>
        </div>
      </div>
    </article>
  `).join("");
}

// Cart Actions
function addToCart(productId) {
  const product = INITIAL_PRODUCTS.find(p => p.id === productId);
  if (!product) return;

  const existingIndex = cart.findIndex(item => item.id === productId);
  if (existingIndex > -1) {
    cart[existingIndex].quantity += 1;
  } else {
    cart.push({
      id: product.id,
      name: product.name,
      price: product.price,
      image: product.image,
      category: product.category,
      quantity: 1
    });
  }

  saveCart();
  updateCartUI();
  showToast(`Added "${product.name}" to cart`, "success");
}

function updateCartQuantity(productId, delta) {
  const index = cart.findIndex(item => item.id === productId);
  if (index === -1) return;

  cart[index].quantity += delta;
  if (cart[index].quantity <= 0) {
    cart.splice(index, 1);
  }

  saveCart();
  updateCartUI();
}

function removeFromCart(productId) {
  cart = cart.filter(item => item.id !== productId);
  saveCart();
  updateCartUI();
  showToast("Item removed from cart", "info");
}

// Update Cart Drawer UI
function updateCartUI() {
  const countEl = document.getElementById("cartCount");
  const itemsContainer = document.getElementById("cartItems");
  const subtotalEl = document.getElementById("cartSubtotal");
  const shippingEl = document.getElementById("cartShipping");
  const taxEl = document.getElementById("cartTax");
  const totalEl = document.getElementById("cartTotal");
  const checkoutBtn = document.getElementById("btnProceedCheckout");

  const totalQuantity = cart.reduce((sum, item) => sum + item.quantity, 0);
  if (countEl) countEl.textContent = totalQuantity;

  const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  const shipping = subtotal > 0 && subtotal < CONFIG.freeShippingThreshold ? CONFIG.shippingFee : 0;
  const tax = subtotal * CONFIG.taxRate;
  const grandTotal = subtotal + shipping + tax;

  if (subtotalEl) subtotalEl.textContent = `${CONFIG.currency}${subtotal.toFixed(2)}`;
  if (shippingEl) shippingEl.textContent = shipping === 0 ? "FREE" : `${CONFIG.currency}${shipping.toFixed(2)}`;
  if (taxEl) taxEl.textContent = `${CONFIG.currency}${tax.toFixed(2)}`;
  if (totalEl) totalEl.textContent = `${CONFIG.currency}${grandTotal.toFixed(2)}`;

  if (checkoutBtn) {
    checkoutBtn.disabled = cart.length === 0;
    checkoutBtn.style.opacity = cart.length === 0 ? "0.5" : "1";
    checkoutBtn.style.pointerEvents = cart.length === 0 ? "none" : "auto";
  }

  if (!itemsContainer) return;

  if (cart.length === 0) {
    itemsContainer.innerHTML = `
      <div class="cart-empty">
        <div class="cart-empty-icon">🛒</div>
        <p style="font-weight: 600; margin-bottom: 0.3rem;">Your cart is empty</p>
        <p style="font-size: 0.85rem; color: var(--text-secondary);">Browse items and add them to your shopping bag.</p>
      </div>
    `;
    return;
  }

  itemsContainer.innerHTML = cart.map(item => `
    <div class="cart-item">
      <img src="${item.image}" alt="${item.name}" class="cart-item-img" />
      <div class="cart-item-details">
        <div class="cart-item-name">${item.name}</div>
        <div class="cart-item-price">${CONFIG.currency}${(item.price * item.quantity).toFixed(2)}</div>
        <div class="cart-item-controls">
          <div class="qty-stepper">
            <button class="qty-btn" onclick="updateCartQuantity('${item.id}', -1)">-</button>
            <span class="qty-val">${item.quantity}</span>
            <button class="qty-btn" onclick="updateCartQuantity('${item.id}', 1)">+</button>
          </div>
          <button class="btn-remove-item" onclick="removeFromCart('${item.id}')">Remove</button>
        </div>
      </div>
    </div>
  `).join("");
}

// Setup Event Listeners
function setupEventListeners() {
  // Cart Drawer toggles
  const cartBtn = document.getElementById("cartToggleBtn");
  const cartDrawer = document.getElementById("cartDrawer");
  const backdrop = document.getElementById("drawerBackdrop");
  const closeCartBtn = document.getElementById("closeCartBtn");

  const openCart = () => {
    cartDrawer.classList.add("active");
    backdrop.classList.add("active");
  };

  const closeCart = () => {
    cartDrawer.classList.remove("active");
    backdrop.classList.remove("active");
  };

  cartBtn?.addEventListener("click", openCart);
  closeCartBtn?.addEventListener("click", closeCart);
  backdrop?.addEventListener("click", () => {
    closeCart();
    closeCheckoutModal();
    closeApiSettingsModal();
  });

  // Search input
  const searchInput = document.getElementById("searchInput");
  searchInput?.addEventListener("input", (e) => {
    searchQuery = e.target.value.trim();
    renderProducts();
  });

  // Checkout modal toggles
  const checkoutBtn = document.getElementById("btnProceedCheckout");
  const checkoutModal = document.getElementById("checkoutModal");
  const closeCheckoutBtn = document.getElementById("closeCheckoutBtn");

  checkoutBtn?.addEventListener("click", () => {
    closeCart();
    checkoutModal.classList.add("active");
    backdrop.classList.add("active");
    updateCheckoutSummaryReview();
  });

  closeCheckoutBtn?.addEventListener("click", closeCheckoutModal);

  // API Config modal toggles
  const apiBadge = document.getElementById("apiConfigBadge");
  const apiModal = document.getElementById("apiSettingsModal");
  const closeApiBtn = document.getElementById("closeApiModalBtn");

  apiBadge?.addEventListener("click", () => {
    updateApiInspectorUI();
    apiModal.classList.add("active");
    backdrop.classList.add("active");
  });

  closeApiBtn?.addEventListener("click", closeApiSettingsModal);

  // Checkout form submit
  const checkoutForm = document.getElementById("checkoutForm");
  checkoutForm?.addEventListener("submit", handleCheckoutSubmission);

  // API Test endpoint trigger
  const testEndpointBtn = document.getElementById("testEndpointBtn");
  testEndpointBtn?.addEventListener("click", testEndpointConnection);
}

function closeCheckoutModal() {
  document.getElementById("checkoutModal")?.classList.remove("active");
  document.getElementById("drawerBackdrop")?.classList.remove("active");
}

function closeApiSettingsModal() {
  document.getElementById("apiSettingsModal")?.classList.remove("active");
  document.getElementById("drawerBackdrop")?.classList.remove("active");
}

// Review calculation for checkout modal
function updateCheckoutSummaryReview() {
  const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  const shipping = subtotal > 0 && subtotal < CONFIG.freeShippingThreshold ? CONFIG.shippingFee : 0;
  const tax = subtotal * CONFIG.taxRate;
  const grandTotal = subtotal + shipping + tax;

  const summaryEl = document.getElementById("modalOrderSummary");
  if (summaryEl) {
    summaryEl.innerHTML = `
      <div style="font-size: 0.88rem; color: var(--text-secondary); display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
        <span>Items (${cart.reduce((c, i) => c + i.quantity, 0)}):</span>
        <span style="color: var(--text-primary);">${CONFIG.currency}${subtotal.toFixed(2)}</span>
      </div>
      <div style="font-size: 0.88rem; color: var(--text-secondary); display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
        <span>Shipping:</span>
        <span style="color: var(--text-primary);">${shipping === 0 ? "FREE" : CONFIG.currency + shipping.toFixed(2)}</span>
      </div>
      <div style="font-size: 0.88rem; color: var(--text-secondary); display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
        <span>Estimated Tax:</span>
        <span style="color: var(--text-primary);">${CONFIG.currency}${tax.toFixed(2)}</span>
      </div>
      <div style="font-size: 1.05rem; font-weight: 800; color: #818cf8; display: flex; justify-content: space-between; border-top: 1px dashed var(--border-color); padding-top: 0.5rem; margin-top: 0.5rem;">
        <span>Total Payable:</span>
        <span>${CONFIG.currency}${grandTotal.toFixed(2)}</span>
      </div>
    `;
  }
}

// Handle Order Submission & Forward to External API
async function handleCheckoutSubmission(e) {
  e.preventDefault();
  const form = e.target;
  const submitBtn = document.getElementById("btnSubmitOrder");
  const originalBtnText = submitBtn.innerHTML;

  // Build Payload
  const formData = new FormData(form);
  const customerInfo = {
    fullName: formData.get("fullName"),
    email: formData.get("email"),
    phone: formData.get("phone"),
    address: {
      line1: formData.get("addressLine1"),
      line2: formData.get("addressLine2") || "",
      city: formData.get("city"),
      state: formData.get("state"),
      postalCode: formData.get("postalCode"),
      country: formData.get("country")
    },
    paymentMethod: formData.get("paymentMethod") || "Credit Card",
    notes: formData.get("orderNotes") || ""
  };

  // Send strictly orderid, productname, and time with the exact product name(s)
  const productNames = cart.map(item => item.name).join(", ");

  const orderPayload = {
    orderid: "ORD-" + Date.now().toString(36).toUpperCase() + "-" + Math.floor(Math.random() * 899 + 100),
    productname: productNames,
    time: new Date().toISOString()
  };

  try {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `
      <svg class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" style="opacity: 0.25; fill: none;"></circle>
        <path d="M4 12a8 8 0 018-8v8H4z" fill="currentColor"></path>
      </svg>
      Forwarding Order to API...
    `;

    console.log("Sending order payload to external API:", CONFIG.ORDER_API_ENDPOINT, orderPayload);

    let responseData = null;
    let isSuccess = false;

    // Send HTTP POST to the configured destination
    try {
      const response = await fetch(CONFIG.ORDER_API_ENDPOINT, {
        method: "POST",
        headers: CONFIG.API_HEADERS,
        body: JSON.stringify(orderPayload)
      });

      if (response.ok) {
        responseData = await response.json().catch(() => ({ status: "OK", statusText: response.statusText }));
        isSuccess = true;
      } else {
        throw new Error(`API responded with status ${response.status}: ${response.statusText}`);
      }
    } catch (networkError) {
      console.warn("External API call did not succeed:", networkError);

      if (CONFIG.ALLOW_OFFLINE_SIMULATION) {
        // Fallback simulation mode so user experience isn't broken while testing or configuring
        console.log("Running in fallback simulation mode since endpoint is in testing/mock state.");
        await new Promise(res => setTimeout(res, 800));
        responseData = { simulated: true, originalPayload: orderPayload, notice: "Simulated response" };
        isSuccess = true;
      } else {
        throw networkError;
      }
    }

    if (isSuccess) {
      // Clear Cart
      cart = [];
      saveCart();
      updateCartUI();
      form.reset();

      // Show Order Confirmation Screen
      showOrderSuccessScreen(orderPayload, responseData);
    }

  } catch (error) {
    console.error("Order processing failed:", error);
    showToast(`Order failed: ${error.message}`, "error");
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalBtnText;
  }
}

// Display Order Success Details & API Payload confirmation
function showOrderSuccessScreen(orderPayload, apiResponse) {
  const modal = document.getElementById("checkoutModal");
  if (!modal) return;

  const content = modal.querySelector(".modal-card");
  content.innerHTML = `
    <div class="order-success-view">
      <div class="order-success-icon">✓</div>
      <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 0.5rem;">Order Placed Successfully!</h2>
      <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">
        Order <strong style="color: #818cf8;">#${orderPayload.orderid}</strong> has been processed and forwarded to your external endpoint.
      </p>

      <div style="background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1.25rem; text-align: left; margin-bottom: 1.5rem;">
        <div style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: #818cf8; margin-bottom: 0.5rem;">
          External API Dispatch Summary
        </div>
        <p style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
          <strong>Destination URL:</strong> <code style="color: #38bdf8;">${CONFIG.ORDER_API_ENDPOINT}</code>
        </p>
        <p style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 0.75rem;">
          <strong>Product Name:</strong> ${orderPayload.productname}
        </p>

        <div style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted); margin-bottom: 0.25rem;">
          JSON Payload Sent:
        </div>
        <pre class="code-preview" style="max-height: 180px;">${escapeHtml(JSON.stringify(orderPayload, null, 2))}</pre>
      </div>

      <button class="btn-checkout" onclick="window.location.reload()">
        Back to Store
      </button>
    </div>
  `;
}

// API Inspector modal helper
function updateApiInspectorUI() {
  const endpointDisplay = document.getElementById("currentEndpointDisplay");
  const codePreview = document.getElementById("samplePayloadPreview");
  if (endpointDisplay) endpointDisplay.value = CONFIG.ORDER_API_ENDPOINT;

  const samplePayload = {
    orderid: "ORD-K98X12-304",
    productname: "Oven",
    time: new Date().toISOString()
  };

  if (codePreview) {
    codePreview.textContent = JSON.stringify(samplePayload, null, 2);
  }
}

// Quick Endpoint Test Connection Button
async function testEndpointConnection() {
  const input = document.getElementById("currentEndpointDisplay");
  const targetUrl = input ? input.value.trim() : CONFIG.ORDER_API_ENDPOINT;
  const statusBox = document.getElementById("endpointTestResult");

  if (!targetUrl) {
    showToast("Please provide a valid URL", "error");
    return;
  }

  statusBox.style.display = "block";
  statusBox.innerHTML = `<span style="color: #818cf8;">Pinging ${targetUrl}...</span>`;

  try {
    const res = await fetch(targetUrl, {
      method: "POST",
      headers: CONFIG.API_HEADERS,
      body: JSON.stringify({ ping: true, test: true, timestamp: Date.now() })
    });

    if (res.ok) {
      statusBox.innerHTML = `<span style="color: var(--success); font-weight: 600;">✓ Connected successfully! Status: ${res.status} ${res.statusText}</span>`;
      // Update config and persist to localStorage
      CONFIG.ORDER_API_ENDPOINT = targetUrl;
      localStorage.setItem("novastore_api_endpoint", targetUrl);
      updateEndpointStatusBadge();
      showToast("Endpoint verified and saved!", "success");
    } else {
      statusBox.innerHTML = `<span style="color: var(--danger);">⚠ Server responded with HTTP ${res.status}: ${res.statusText}</span>`;
    }
  } catch (err) {
    statusBox.innerHTML = `
      <div style="color: var(--danger); line-height: 1.4;">
        <strong>✕ Connection failed:</strong> ${err.message}<br>
        <span style="font-size: 0.75rem; color: var(--text-muted);">
          Tips: 1. Check if Laptop 2's server is running. 2. Verify Laptop 2's Wi-Fi IP and port. 3. Ensure Laptop 2's firewall allows inbound connections.
        </span>
      </div>
    `;
  }
}

function updateEndpointStatusBadge() {
  const badge = document.getElementById("apiConfigBadge");
  if (!badge) return;
  try {
    const url = new URL(CONFIG.ORDER_API_ENDPOINT);
    badge.title = `Forwarding orders to: ${CONFIG.ORDER_API_ENDPOINT}`;
  } catch(e) {
    // fallback
  }
}

// Toast utility
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
    <span>${message}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

// Escape HTML helper for previewing JSON
function escapeHtml(string) {
  return String(string)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
