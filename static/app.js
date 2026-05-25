const state = {
  categories: [],
  products: [],
  cart: loadCart(),
  activeCategory: "all",
  search: "",
  activeView: "menu",
};

const statusLabels = {
  new: "Yangi",
  accepted: "Qabul qilindi",
  preparing: "Tayyorlanmoqda",
  on_way: "Yetkazilmoqda",
  delivered: "Yetkazildi",
  cancelled: "Bekor qilindi",
};

const elements = {
  menuView: document.querySelector("#menuView"),
  adminView: document.querySelector("#adminView"),
  categoryList: document.querySelector("#categoryList"),
  productGrid: document.querySelector("#productGrid"),
  productSearch: document.querySelector("#productSearch"),
  cartItems: document.querySelector("#cartItems"),
  subtotalValue: document.querySelector("#subtotalValue"),
  deliveryValue: document.querySelector("#deliveryValue"),
  discountValue: document.querySelector("#discountValue"),
  totalValue: document.querySelector("#totalValue"),
  clearCartButton: document.querySelector("#clearCartButton"),
  checkoutButton: document.querySelector("#checkoutButton"),
  checkoutModal: document.querySelector("#checkoutModal"),
  checkoutForm: document.querySelector("#checkoutForm"),
  closeModalButton: document.querySelector("#closeModalButton"),
  cancelCheckoutButton: document.querySelector("#cancelCheckoutButton"),
  formMessage: document.querySelector("#formMessage"),
  toast: document.querySelector("#toast"),
  refreshAdminButton: document.querySelector("#refreshAdminButton"),
  statsGrid: document.querySelector("#statsGrid"),
  ordersTableBody: document.querySelector("#ordersTableBody"),
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindEvents();
  await loadCatalog();
  renderCart();
}

function bindEvents() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });

  elements.productSearch.addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    renderProducts();
  });

  elements.categoryList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-category]");
    if (!button) return;
    state.activeCategory = button.dataset.category;
    renderCategories();
    renderProducts();
  });

  elements.productGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-add]");
    if (!button) return;
    addToCart(Number(button.dataset.add));
  });

  elements.cartItems.addEventListener("click", (event) => {
    const button = event.target.closest("[data-cart-action]");
    if (!button) return;
    const productId = Number(button.dataset.productId);
    const action = button.dataset.cartAction;
    if (action === "increase") changeQuantity(productId, 1);
    if (action === "decrease") changeQuantity(productId, -1);
    if (action === "remove") removeFromCart(productId);
  });

  elements.clearCartButton.addEventListener("click", () => {
    state.cart = [];
    saveCart();
    renderCart();
  });

  elements.checkoutButton.addEventListener("click", openCheckout);
  elements.closeModalButton.addEventListener("click", closeCheckout);
  elements.cancelCheckoutButton.addEventListener("click", closeCheckout);
  elements.checkoutModal.addEventListener("click", (event) => {
    if (event.target === elements.checkoutModal) closeCheckout();
  });
  elements.checkoutForm.addEventListener("submit", submitOrder);
  elements.refreshAdminButton.addEventListener("click", loadAdmin);

  elements.ordersTableBody.addEventListener("change", async (event) => {
    const select = event.target.closest("[data-order-status]");
    if (!select) return;
    await changeOrderStatus(Number(select.dataset.orderStatus), select.value);
  });
}

async function loadCatalog() {
  setProductsLoading();
  try {
    const [categoriesResponse, productsResponse] = await Promise.all([
      api("/api/categories"),
      api("/api/products"),
    ]);
    state.categories = categoriesResponse.categories;
    state.products = productsResponse.products;
    renderCategories();
    renderProducts();
  } catch (error) {
    elements.productGrid.innerHTML = emptyState(error.message);
  }
}

function renderCategories() {
  const allButton = categoryButton("all", "Barchasi", state.activeCategory === "all");
  const categoryButtons = state.categories
    .map((category) => categoryButton(category.slug, category.name, state.activeCategory === category.slug))
    .join("");
  elements.categoryList.innerHTML = allButton + categoryButtons;
}

function renderProducts() {
  const search = state.search.toLowerCase();
  const products = state.products.filter((product) => {
    const matchesCategory = state.activeCategory === "all" || product.category_slug === state.activeCategory;
    const text = `${product.name} ${product.description}`.toLowerCase();
    const matchesSearch = !search || text.includes(search);
    return matchesCategory && matchesSearch;
  });

  if (!products.length) {
    elements.productGrid.innerHTML = emptyState("Bu bo'limda mahsulot topilmadi");
    return;
  }

  elements.productGrid.innerHTML = products.map(productCard).join("");
}

function productCard(product) {
  const badges = [
    product.is_popular ? '<span class="badge popular">Top</span>' : "",
    product.is_spicy ? '<span class="badge hot">Achchiq</span>' : "",
    `<span class="badge">${escapeHtml(product.weight)}</span>`,
    `<span class="badge">${Number(product.calories)} kkal</span>`,
  ].join("");

  return `
    <article class="product-card">
      <img src="${escapeAttribute(product.image_url)}" alt="${escapeAttribute(product.name)}">
      <div class="product-body">
        <div class="product-title-row">
          <h3>${escapeHtml(product.name)}</h3>
          <span class="price">${formatMoney(product.price)}</span>
        </div>
        <div class="badge-row">${badges}</div>
        <p class="product-description">${escapeHtml(product.description)}</p>
        <div class="product-footer">
          <span>${escapeHtml(product.category_name)}</span>
          <button class="add-button" type="button" data-add="${product.id}" aria-label="${escapeAttribute(product.name)} savatga qo'shish" title="Savatga qo'shish">+</button>
        </div>
      </div>
    </article>
  `;
}

function renderCart() {
  const cartLines = cartLinesWithProducts();
  if (!cartLines.length) {
    elements.cartItems.innerHTML = "<div class=\"cart-empty\">Savat bo'sh</div>";
  } else {
    elements.cartItems.innerHTML = cartLines.map(cartLine).join("");
  }

  const totals = calculateTotals(cartLines);
  elements.subtotalValue.textContent = formatMoney(totals.subtotal);
  elements.deliveryValue.textContent = totals.deliveryFee ? formatMoney(totals.deliveryFee) : "Bepul";
  elements.discountValue.textContent = totals.discount ? `-${formatMoney(totals.discount)}` : "0 so'm";
  elements.totalValue.textContent = formatMoney(totals.total);
  elements.checkoutButton.disabled = cartLines.length === 0;
  elements.clearCartButton.disabled = cartLines.length === 0;
}

function cartLine(line) {
  return `
    <article class="cart-line">
      <img src="${escapeAttribute(line.product.image_url)}" alt="${escapeAttribute(line.product.name)}">
      <div>
        <h3>${escapeHtml(line.product.name)}</h3>
        <p>${formatMoney(line.product.price)} x ${line.quantity}</p>
      </div>
      <div class="qty-control" aria-label="${escapeAttribute(line.product.name)} soni">
        <button class="qty-button" type="button" data-cart-action="decrease" data-product-id="${line.product.id}" aria-label="Kamaytirish" title="Kamaytirish">-</button>
        <span class="qty-value">${line.quantity}</span>
        <button class="qty-button" type="button" data-cart-action="increase" data-product-id="${line.product.id}" aria-label="Ko'paytirish" title="Ko'paytirish">+</button>
      </div>
    </article>
  `;
}

function addToCart(productId) {
  const existing = state.cart.find((item) => item.productId === productId);
  if (existing) {
    existing.quantity = Math.min(existing.quantity + 1, 20);
  } else {
    state.cart.push({ productId, quantity: 1 });
  }
  saveCart();
  renderCart();
  showToast("Savat yangilandi");
}

function changeQuantity(productId, delta) {
  const item = state.cart.find((cartItem) => cartItem.productId === productId);
  if (!item) return;
  item.quantity += delta;
  if (item.quantity <= 0) removeFromCart(productId);
  if (item.quantity > 20) item.quantity = 20;
  saveCart();
  renderCart();
}

function removeFromCart(productId) {
  state.cart = state.cart.filter((item) => item.productId !== productId);
  saveCart();
  renderCart();
}

function cartLinesWithProducts() {
  return state.cart
    .map((item) => ({
      product: state.products.find((product) => product.id === item.productId),
      quantity: item.quantity,
    }))
    .filter((line) => line.product);
}

function calculateTotals(lines) {
  const subtotal = lines.reduce((sum, line) => sum + line.product.price * line.quantity, 0);
  const deliveryFee = subtotal === 0 || subtotal >= 120000 ? 0 : 15000;
  const discount = subtotal >= 250000 ? Math.round(subtotal * 0.1) : 0;
  return {
    subtotal,
    deliveryFee,
    discount,
    total: subtotal + deliveryFee - discount,
  };
}

function openCheckout() {
  if (!state.cart.length) return;
  elements.formMessage.textContent = "";
  elements.checkoutModal.classList.remove("hidden");
  elements.checkoutForm.customer_name.focus();
}

function closeCheckout() {
  elements.checkoutModal.classList.add("hidden");
}

async function submitOrder(event) {
  event.preventDefault();
  elements.formMessage.textContent = "";
  const submitButton = elements.checkoutForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;

  const formData = new FormData(elements.checkoutForm);
  const payload = {
    customer_name: formData.get("customer_name"),
    phone: formData.get("phone"),
    address: formData.get("address"),
    payment_method: formData.get("payment_method"),
    delivery_type: formData.get("delivery_type"),
    comment: formData.get("comment"),
    items: state.cart.map((item) => ({
      product_id: item.productId,
      quantity: item.quantity,
    })),
  };

  try {
    const response = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.cart = [];
    saveCart();
    renderCart();
    closeCheckout();
    elements.checkoutForm.reset();
    showToast(`Buyurtma qabul qilindi: ${response.order.order_number}`);
    if (state.activeView === "admin") await loadAdmin();
  } catch (error) {
    elements.formMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function setView(viewName) {
  state.activeView = viewName;
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
  elements.menuView.classList.toggle("hidden", viewName !== "menu");
  elements.adminView.classList.toggle("hidden", viewName !== "admin");
  if (viewName === "admin") await loadAdmin();
}

async function loadAdmin() {
  elements.statsGrid.innerHTML = "";
  elements.ordersTableBody.innerHTML = `<tr><td colspan="5">Yuklanmoqda...</td></tr>`;
  try {
    const [dashboard, ordersResponse] = await Promise.all([
      api("/api/admin/dashboard"),
      api("/api/admin/orders?limit=50"),
    ]);
    renderStats(dashboard);
    renderOrders(ordersResponse.orders);
  } catch (error) {
    elements.ordersTableBody.innerHTML = `<tr><td colspan="5">${escapeHtml(error.message)}</td></tr>`;
  }
}

function renderStats(dashboard) {
  const statusText = dashboard.statuses.length
    ? dashboard.statuses.map((item) => `${statusLabels[item.status] || item.status}: ${item.total}`).join(" | ")
    : "Hali buyurtma yo'q";

  elements.statsGrid.innerHTML = [
    statCard("Buyurtmalar", dashboard.orders_count),
    statCard("Daromad", formatMoney(dashboard.revenue)),
    statCard("O'rtacha chek", formatMoney(Math.round(dashboard.average_check))),
    statCard("Statuslar", statusText),
  ].join("");
}

function renderOrders(orders) {
  if (!orders.length) {
    elements.ordersTableBody.innerHTML = `<tr><td colspan="5">Hali buyurtma yo'q</td></tr>`;
    return;
  }

  elements.ordersTableBody.innerHTML = orders
    .map((order) => {
      return `
        <tr>
          <td><strong>${escapeHtml(order.order_number)}</strong></td>
          <td>
            ${escapeHtml(order.customer_name)}
            <br>
            <small>${escapeHtml(order.phone)} | ${order.unit_count} ta mahsulot</small>
          </td>
          <td>
            <select class="status-select" data-order-status="${order.id}" aria-label="Buyurtma statusi">
              ${Object.entries(statusLabels)
                .map(([value, label]) => `<option value="${value}" ${order.status === value ? "selected" : ""}>${label}</option>`)
                .join("")}
            </select>
          </td>
          <td>${formatMoney(order.total)}</td>
          <td>${formatDate(order.created_at)}</td>
        </tr>
      `;
    })
    .join("");
}

async function changeOrderStatus(orderId, status) {
  try {
    await api(`/api/admin/orders/${orderId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    showToast("Status yangilandi");
    await loadAdmin();
  } catch (error) {
    showToast(error.message);
    await loadAdmin();
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error?.message || "Server xatoligi");
  }
  return payload;
}

function categoryButton(slug, name, isActive) {
  return `
    <button class="category-chip ${isActive ? "active" : ""}" type="button" data-category="${escapeAttribute(slug)}">
      ${escapeHtml(name)}
    </button>
  `;
}

function statCard(label, value) {
  return `
    <article class="stat-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value))}</strong>
    </article>
  `;
}

function emptyState(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function setProductsLoading() {
  elements.productGrid.innerHTML = emptyState("Menyu yuklanmoqda...");
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.classList.add("hidden");
  }, 2600);
}

function loadCart() {
  try {
    const rawCart = JSON.parse(localStorage.getItem("maxway-cart") || "[]");
    if (!Array.isArray(rawCart)) return [];
    return rawCart
      .map((item) => ({
        productId: Number(item.productId),
        quantity: Number(item.quantity),
      }))
      .filter((item) => item.productId > 0 && item.quantity > 0);
  } catch {
    return [];
  }
}

function saveCart() {
  localStorage.setItem("maxway-cart", JSON.stringify(state.cart));
}

function formatMoney(value) {
  return `${Number(value).toLocaleString("uz-UZ")} so'm`;
}

function formatDate(value) {
  return new Date(value).toLocaleString("uz-UZ", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}
