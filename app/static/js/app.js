const state = {
  menu: [],
  activeCategory: "Todos",
  cart: new Map(), // product_id -> qty
  lastParsed: null,
};

const fmtBRL = (v) =>
  Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const STATUS_LABELS = {
  recebido: "Recebido",
  em_preparo: "Em preparo",
  saiu_para_entrega: "Saiu p/ entrega",
  entregue: "Entregue",
  cancelado: "Cancelado",
};

const NEXT_STATUS = {
  recebido: { next: "em_preparo", label: "Iniciar Preparo" },
  em_preparo: { next: "saiu_para_entrega", label: "Enviar p/ Entrega" },
  saiu_para_entrega: { next: "entregue", label: "Marcar Entregue" },
};

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Erro na requisição");
  }
  return data;
}

function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === `tab-${tabName}`);
  });
  if (tabName === "admin") loadAdmin();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateCartBadge() {
  let count = 0;
  for (const qty of state.cart.values()) count += qty;
  const badge = document.getElementById("nav-cart-badge");
  const clearBtn = document.getElementById("btn-clear-cart");
  if (count > 0) {
    badge.textContent = String(count);
    badge.classList.remove("hidden");
    clearBtn.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
    clearBtn.classList.add("hidden");
  }
}

async function loadHealth() {
  try {
    const h = await api("/api/health");
    const pillAi = document.getElementById("pill-ai");
    const pillTg = document.getElementById("pill-tg");
    const engineBadge = document.getElementById("ai-engine-badge");

    if (h.ai_mode === "gemini") {
      pillAi.textContent = "IA: Gemini";
      pillAi.className = "status-dot live";
      engineBadge.textContent = "Google Gemini Ativo";
      engineBadge.className = "engine-pill live";
    } else {
      pillAi.textContent = "IA: Demo";
      pillAi.className = "status-dot";
      engineBadge.textContent = "Modo Demo Offline";
      engineBadge.className = "engine-pill";
    }

    if (h.telegram_mode === "live") {
      pillTg.textContent = "Telegram: Live";
      pillTg.className = "engine-pill live";
    } else {
      pillTg.textContent = "Telegram: Log Local";
      pillTg.className = "engine-pill";
    }
  } catch (e) {
    console.error(e);
  }
}

async function loadMenu() {
  state.menu = await api("/api/menu");
  renderHomeFeatured();
  renderCategories();
  renderMenu();
}

function renderHomeFeatured() {
  const grid = document.getElementById("home-featured-grid");
  const picks = [
    state.menu.find((p) => p.category === "Pizzas"),
    state.menu.find((p) => p.category === "Açaí"),
    state.menu.find((p) => p.category === "Combos") || state.menu[2],
  ].filter(Boolean);

  grid.innerHTML = picks
    .map(
      (p) => `
      <article class="product-card">
        <img src="${p.image_url || "/static/images/combo_pizza_acai.jpg"}" alt="${p.name}" class="product-img">
        <div class="product-body">
          <span class="product-cat">${p.category}</span>
          <h3 class="product-title">${p.name}</h3>
          <p class="product-desc">${p.description}</p>
          <div class="product-foot">
            <span class="price">${fmtBRL(p.price)}</span>
            <button class="btn btn-primary btn-sm" data-quick-add="${p.id}">Pedir agora</button>
          </div>
        </div>
      </article>`
    )
    .join("");

  grid.querySelectorAll("[data-quick-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.quickAdd);
      state.cart.set(id, (state.cart.get(id) || 0) + 1);
      renderCart();
      switchTab("menu");
    });
  });
}

function renderCategories() {
  const cats = ["Todos", ...new Set(state.menu.map((p) => p.category))];
  const container = document.getElementById("category-filters");
  container.innerHTML = cats
    .map(
      (c) =>
        `<button class="filter-pill ${c === state.activeCategory ? "active" : ""}" data-cat="${c}">${c}</button>`
    )
    .join("");
  container.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeCategory = btn.dataset.cat;
      renderCategories();
      renderMenu();
    });
  });
}

function renderMenu() {
  const grid = document.getElementById("menu-grid");
  const filtered =
    state.activeCategory === "Todos"
      ? state.menu
      : state.menu.filter((p) => p.category === state.activeCategory);

  grid.innerHTML = filtered
    .map(
      (p) => `
      <article class="product-card">
        <img src="${p.image_url || "/static/images/combo_pizza_acai.jpg"}" alt="${p.name}" class="product-img">
        <div class="product-body">
          <span class="product-cat">${p.category}</span>
          <h3 class="product-title">${p.name}</h3>
          <p class="product-desc">${p.description}</p>
          <div class="product-foot">
            <span class="price">${fmtBRL(p.price)}</span>
            <button class="btn btn-primary btn-sm" data-add="${p.id}">+ Adicionar</button>
          </div>
        </div>
      </article>`
    )
    .join("");

  grid.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.add);
      state.cart.set(id, (state.cart.get(id) || 0) + 1);
      renderCart();
    });
  });
}

function renderCart() {
  const container = document.getElementById("cart-items");
  const totalEl = document.getElementById("cart-total");
  updateCartBadge();

  if (state.cart.size === 0) {
    container.innerHTML =
      '<p class="empty-msg">Seu carrinho está vazio. Adicione itens do cardápio ao lado.</p>';
    totalEl.textContent = fmtBRL(0);
    return;
  }

  let total = 0;
  const rows = [];
  for (const [id, qty] of state.cart.entries()) {
    const p = state.menu.find((m) => m.id === id);
    if (!p) continue;
    const sub = p.price * qty;
    total += sub;
    rows.push(`
      <div class="cart-row">
        <div>
          <strong>${p.name}</strong><br>
          <span class="empty-msg">${fmtBRL(p.price)} × ${qty} = ${fmtBRL(sub)}</span>
        </div>
        <div class="qty-controls">
          <button class="qty-btn" data-dec="${id}">−</button>
          <span>${qty}</span>
          <button class="qty-btn" data-inc="${id}">+</button>
        </div>
      </div>
    `);
  }
  container.innerHTML = rows.join("");
  totalEl.textContent = fmtBRL(total);

  container.querySelectorAll("[data-inc]").forEach((b) =>
    b.addEventListener("click", () => {
      const id = Number(b.dataset.inc);
      state.cart.set(id, (state.cart.get(id) || 0) + 1);
      renderCart();
    })
  );
  container.querySelectorAll("[data-dec]").forEach((b) =>
    b.addEventListener("click", () => {
      const id = Number(b.dataset.dec);
      const next = (state.cart.get(id) || 0) - 1;
      if (next <= 0) state.cart.delete(id);
      else state.cart.set(id, next);
      renderCart();
    })
  );
}

document.getElementById("btn-clear-cart").addEventListener("click", () => {
  state.cart.clear();
  renderCart();
});

// --- Checkout ---
document.getElementById("checkout-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fb = document.getElementById("checkout-feedback");
  fb.className = "feedback hidden";

  if (state.cart.size === 0) {
    fb.textContent = "Adicione pelo menos 1 item ao carrinho.";
    fb.className = "feedback err";
    return;
  }

  const payload = {
    customer_name: document.getElementById("cust-name").value,
    customer_phone: document.getElementById("cust-phone").value || null,
    delivery_address: document.getElementById("cust-address").value,
    payment_method: document.getElementById("cust-payment").value,
    notes: document.getElementById("cust-notes").value || null,
    channel: "web",
    items: Array.from(state.cart.entries()).map(([product_id, quantity]) => ({
      product_id,
      quantity,
    })),
  };

  try {
    const order = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.cart.clear();
    renderCart();
    e.target.reset();
    const tgMode = order.notifications?.[0]?.mode || "simulated";
    fb.textContent = `Pedido #${order.id} confirmado (${fmtBRL(order.total_amount)})! Notificação Telegram: ${tgMode}.`;
    fb.className = "feedback ok";
  } catch (err) {
    fb.textContent = err.message;
    fb.className = "feedback err";
  }
});

// --- AI Assistant ---
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.getElementById("ai-message").value = chip.dataset.example;
    document.getElementById("ai-form").dispatchEvent(new Event("submit"));
  });
});

document.getElementById("ai-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("ai-message").value.trim();
  if (!msg) return;

  const btn = document.getElementById("ai-submit-btn");
  const box = document.getElementById("ai-result");
  btn.disabled = true;
  btn.textContent = "Analisando...";

  try {
    const parsed = await api("/api/assistant/parse", {
      method: "POST",
      body: JSON.stringify({ message: msg, auto_create: false }),
    });
    state.lastParsed = { message: msg, parsed };
    renderAiPreview(parsed);
  } catch (err) {
    box.className = "ai-result";
    box.innerHTML = `<p style="color:#b91c1c">Erro: ${err.message}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Montar Pedido";
  }
});

function renderAiPreview(p) {
  const box = document.getElementById("ai-result");
  box.className = "ai-result";

  const itemsHtml = p.items.length
    ? p.items
        .map((i) => `<li>${i.quantity}× <strong>${i.product_name}</strong> — ${fmtBRL(i.subtotal)}</li>`)
        .join("")
    : '<li class="empty-msg">Nenhum item identificado</li>';

  const missingHtml = p.missing_fields.length
    ? `<p style="color:#b45309;font-size:0.84rem;font-weight:600;margin-top:6px;">Falta informar: ${p.missing_fields.join(", ")}</p>`
    : `<p style="color:#0f766e;font-size:0.84rem;font-weight:600;margin-top:6px;">Pedido completo e validado!</p>`;

  box.innerHTML = `
    <p><strong>Assistente (${p.engine === "gemini" ? "Gemini" : "Demo Offline"}):</strong> ${p.reply}</p>
    <div class="ai-result-grid">
      <div>
        <span style="font-size:0.75rem;font-weight:700;color:#57534e;">ITENS DO CARDÁPIO</span>
        <ul style="margin:6px 0 0 18px;font-size:0.88rem;">${itemsHtml}</ul>
        <p style="margin-top:8px;"><strong>Total oficial: ${fmtBRL(p.estimated_total)}</strong></p>
      </div>
      <div style="font-size:0.86rem;">
        <span style="font-size:0.75rem;font-weight:700;color:#57534e;">DADOS DE ENTREGA</span>
        <p style="margin-top:6px;">Cliente: <strong>${p.customer_name || "—"}</strong></p>
        <p>Endereço: <strong>${p.delivery_address || "—"}</strong></p>
        <p>Pagamento: <strong>${p.payment_method}</strong></p>
        ${missingHtml}
      </div>
    </div>
    <div class="ai-actions">
      ${
        p.ready_to_confirm
          ? '<button id="btn-ai-confirm" class="btn btn-primary btn-sm">Confirmar Pedido Agora</button>'
          : ""
      }
      ${
        p.items.length
          ? '<button id="btn-ai-to-cart" class="btn btn-outline btn-sm">Editar no Cardápio / Carrinho</button>'
          : ""
      }
    </div>
  `;

  const confirmBtn = document.getElementById("btn-ai-confirm");
  if (confirmBtn) {
    confirmBtn.addEventListener("click", async () => {
      confirmBtn.disabled = true;
      confirmBtn.textContent = "Confirmando...";
      const res = await api("/api/assistant/parse", {
        method: "POST",
        body: JSON.stringify({ message: state.lastParsed.message, auto_create: true }),
      });
      box.innerHTML = `
        <p style="color:#0f766e;font-weight:700;">✅ ${res.reply}</p>
        <p style="font-size:0.84rem;color:#57534e;margin-top:4px;">
          Pedido registrado na aba <strong>Cozinha &amp; BI</strong> com log de notificação Telegram.
        </p>
      `;
    });
  }

  const cartBtn = document.getElementById("btn-ai-to-cart");
  if (cartBtn) {
    cartBtn.addEventListener("click", () => {
      state.cart.clear();
      p.items.forEach((i) => state.cart.set(i.product_id, i.quantity));
      renderCart();
      if (p.customer_name) document.getElementById("cust-name").value = p.customer_name;
      if (p.delivery_address) document.getElementById("cust-address").value = p.delivery_address;
      if (p.payment_method) document.getElementById("cust-payment").value = p.payment_method;
      switchTab("menu");
    });
  }
}

// --- Admin & BI ---
async function loadAdmin() {
  const statusFilter = document.getElementById("status-filter").value;
  const [summary, orders] = await Promise.all([
    api("/api/analytics/summary"),
    api(statusFilter ? `/api/orders?status_filter=${statusFilter}` : "/api/orders"),
  ]);
  renderAnalytics(summary);
  renderOrders(orders);
}

function renderAnalytics(s) {
  const aiCount = s.orders_by_channel?.ai_chat || 0;
  document.getElementById("kpi-grid").innerHTML = `
    <div class="kpi-card accent">
      <div class="kpi-label">Faturamento válido</div>
      <div class="kpi-value">${fmtBRL(s.total_revenue)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Pedidos válidos / total</div>
      <div class="kpi-value">${s.valid_orders} / ${s.total_orders}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Ticket médio</div>
      <div class="kpi-value">${fmtBRL(s.average_ticket)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Pedidos via IA</div>
      <div class="kpi-value">${aiCount}</div>
    </div>
  `;

  const chart = document.getElementById("top-products-chart");
  if (!s.top_products.length) {
    chart.innerHTML = '<p class="empty-msg">Sem vendas registradas ainda.</p>';
  } else {
    const maxRev = Math.max(...s.top_products.map((p) => p.revenue), 1);
    chart.innerHTML = s.top_products
      .map((p) => {
        const pct = Math.round((p.revenue / maxRev) * 100);
        return `
          <div class="bar-row">
            <div class="bar-meta">
              <span>${p.product_name} (${p.quantity_sold} un.)</span>
              <strong>${fmtBRL(p.revenue)}</strong>
            </div>
            <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
          </div>
        `;
      })
      .join("");
  }

  const chChips = Object.entries(s.orders_by_channel || {})
    .map(([k, v]) => `<span class="stat-chip">${k === "ai_chat" ? "Assistente IA" : "Cardápio Web"}: <strong>${v}</strong></span>`)
    .join("");
  const payChips = Object.entries(s.orders_by_payment || {})
    .map(([k, v]) => `<span class="stat-chip">${k}: <strong>${v}</strong></span>`)
    .join("");

  document.getElementById("channel-payment-stats").innerHTML = `
    <div>
      <strong style="color:#57534e;font-size:0.76rem;">POR CANAL</strong>
      <div class="stat-chips">${chChips || '<span class="empty-msg">—</span>'}</div>
    </div>
    <div>
      <strong style="color:#57534e;font-size:0.76rem;">POR FORMA DE PAGAMENTO</strong>
      <div class="stat-chips">${payChips || '<span class="empty-msg">—</span>'}</div>
    </div>
  `;
}

function renderOrders(orders) {
  const list = document.getElementById("orders-list");
  if (!orders.length) {
    list.innerHTML = '<p class="empty-msg">Nenhum pedido encontrado neste filtro.</p>';
    return;
  }

  list.innerHTML = orders
    .map((o) => {
      const itemsText = o.items.map((i) => `${i.quantity}× ${i.product_name}`).join(" • ");
      const next = NEXT_STATUS[o.status];
      const canCancel = !["entregue", "cancelado"].includes(o.status);
      const lastNotif = o.notifications?.[o.notifications.length - 1];

      return `
        <div class="order-row">
          <div class="order-top">
            <div>
              <strong>Pedido #${o.id}</strong> — ${o.customer_name}
              <span class="empty-msg">(${o.channel === "ai_chat" ? "Assistente IA" : "Web"} • ${o.payment_method})</span>
            </div>
            <div>
              <strong style="margin-right:10px;">${fmtBRL(o.total_amount)}</strong>
              <span class="status-badge st-${o.status}">${STATUS_LABELS[o.status] || o.status}</span>
            </div>
          </div>
          <div class="order-meta">
            <div>📍 ${o.delivery_address}</div>
            <div>🍽️ ${itemsText}</div>
          </div>
          <div class="order-actions">
            ${next ? `<button class="btn btn-dark btn-sm" data-status="${o.id}:${next.next}">${next.label}</button>` : ""}
            ${canCancel ? `<button class="btn btn-danger-soft btn-sm" data-status="${o.id}:cancelado">Cancelar</button>` : ""}
          </div>
          ${
            lastNotif
              ? `<details style="margin-top:8px;"><summary style="cursor:pointer;font-size:0.78rem;color:#57534e;">Log Telegram (${lastNotif.mode}) — ${lastNotif.status_detail}</summary><div class="tg-log">${lastNotif.message}</div></details>`
              : ""
          }
        </div>
      `;
    })
    .join("");

  list.querySelectorAll("[data-status]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const [id, status] = btn.dataset.status.split(":");
      await api(`/api/orders/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      loadAdmin();
    });
  });
}

// --- Navigation Events ---
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

document.querySelectorAll("[data-go-tab]").forEach((el) => {
  el.addEventListener("click", () => switchTab(el.dataset.goTab));
});

document.getElementById("btn-focus-ai").addEventListener("click", () => {
  const input = document.getElementById("ai-message");
  document.getElementById("home-ai-box").scrollIntoView({ behavior: "smooth", block: "center" });
  setTimeout(() => input.focus(), 250);
});

document.getElementById("btn-refresh-admin").addEventListener("click", loadAdmin);
document.getElementById("status-filter").addEventListener("change", loadAdmin);

// Init
loadHealth();
loadMenu();
