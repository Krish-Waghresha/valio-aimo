/* Aimo purchasing workspace. Lucide icons (ISC); see icons/LICENSE-lucide.txt.
   Paths are from lucide-static 0.544.0 and are inlined so icon color follows text. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof document !== "undefined") api.mount(document);
  if (typeof window === "undefined" && typeof module !== "undefined") api.selfCheck();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const CSRF_KEY = "aimo.csrf";
  const PENDING_KEY = "aimo.pendingRequest";
  const STOP_POLL = new Set(["ordered_mock", "cancelled", "failed"]);
  const DIET = [
    ["lactose_free", "Lactose-free (not milk-free)"],
    ["gluten_free", "Gluten-free"],
    ["vegan", "Vegan"],
    ["vegetarian", "Vegetarian"]
  ];
  const ALLERGENS = [
    ["gluten_cereals", "Cereals containing gluten"],
    ["crustaceans", "Crustaceans"],
    ["eggs", "Eggs"],
    ["fish", "Fish"],
    ["peanuts", "Peanuts"],
    ["soybeans", "Soybeans"],
    ["milk", "Milk"],
    ["nuts", "Nuts"],
    ["celery", "Celery"],
    ["mustard", "Mustard"],
    ["sesame", "Sesame"],
    ["sulphites", "Sulphites"],
    ["lupin", "Lupin"],
    ["molluscs", "Molluscs"]
  ];
  const PREFERENCES = [
    ["balanced", "Balanced", "Availability, reliability and cost."],
    ["price", "Price", "Lowest quoted purchase cost."],
    ["reliability", "Reliability", "Higher supplied historical reliability first. Not a delivery guarantee."],
    ["sustainability", "Sustainability", "Lower supplied category-average carbon first. Not a product measurement."]
  ];
  const ILLUSTRATIVE = {
    "vegetable-pie": {
      file: "images/vegetable-pie.jpg",
      caption: "Illustrative photo of a mixed-vegetable quiche, not a catalog product or customer image.",
      credit: "E4024, Wikimedia Commons, CC BY-SA 4.0"
    },
    "sweet-pie": {
      file: "images/sweet-pie.jpg",
      caption: "Illustrative photo of an apple pie, not a catalog product or customer image.",
      credit: "Shisma, Wikimedia Commons, CC BY 4.0"
    }
  };
  const ICONS = {
    calendar: '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    "circle-alert": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    "circle-check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    clock: '<path d="M12 6v6l4 2"/><circle cx="12" cy="12" r="10"/>',
    download: '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>',
    history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    leaf: '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
    "log-out": '<path d="m16 17 5-5-5-5"/><path d="M21 12H9"/><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>',
    mic: '<path d="M12 19v3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><rect x="9" y="2" width="6" height="13" rx="3"/>',
    minus: '<path d="M5 12h14"/>',
    pencil: '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "refresh-cw": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    search: '<path d="m21 21-4.34-4.34"/><circle cx="11" cy="11" r="8"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "trash-2": '<path d="M10 11v6"/><path d="M14 11v6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    truck: '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><path d="M16 3.128a4 4 0 0 1 0 7.744"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/>',
    utensils: '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
    wallet: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>'
  };
  const REASONS = {
    REQUEST_BUDGET_EXCEEDED: "Request budget exceeded",
    ORDER_LIMIT_EXCEEDED: "Order limit exceeded",
    DAILY_LIMIT_EXCEEDED: "Shared daily limit exceeded",
    APPROVAL_THRESHOLD_EXCEEDED: "Above the autonomous spend limit",
    PRODUCT_NOT_ELIGIBLE: "Product is not eligible",
    DIETARY_CONFLICT: "Dietary conflict",
    DIETARY_UNCONFIRMED: "Dietary evidence is not confirmed",
    UNIT_UNCONFIRMED: "Unit mapping is not confirmed",
    PRICE_UNAVAILABLE: "Price unavailable",
    PRICE_CHANGED: "Price changed",
    QUANTITY_UNCONFIRMED: "Quantity is not confirmed",
    INSUFFICIENT_STOCK: "Insufficient stock",
    SALES_BLOCK: "Sales block",
    DELIVERY_UNAVAILABLE: "Delivery unavailable",
    DELIVERY_UNCONFIRMED: "Delivery is not confirmed",
    DELIVERY_DATE_MISMATCH: "Offered date does not match the requested date",
    CUTOFF_PASSED: "Order cutoff has passed",
    AUTHORITY_REVOKED: "Authority was revoked"
  };

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }

  function icon(name) {
    return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONS[name] || ""}</svg>`;
  }

  function iconButton(name, action, label, extra) {
    return `<button type="button" class="icon-button" data-action="${esc(action)}" data-tooltip="${esc(label)}" title="${esc(label)}" aria-label="${esc(label)}" ${extra || ""}>${icon(name)}</button>`;
  }

  function uuid() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    const bytes = new Uint8Array(16);
    if (typeof crypto !== "undefined" && crypto.getRandomValues) crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  function addDays(iso, days) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!match) return "";
    const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + days));
    return date.toISOString().slice(0, 10);
  }

  function eurosToMinor(value) {
    const text = String(value ?? "").trim().replace(",", ".");
    if (!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(text)) return null;
    const [whole, frac = ""] = text.split(".");
    return Number(whole) * 100 + Number(frac.padEnd(2, "0"));
  }

  function minorToEuros(minor) {
    if (!Number.isInteger(minor) || minor < 0) return "";
    const cents = String(minor % 100).padStart(2, "0");
    return cents === "00" ? String(Math.floor(minor / 100)) : `${Math.floor(minor / 100)}.${cents}`;
  }

  function formatMinor(minor) {
    if (!Number.isInteger(minor)) return "Not available";
    return new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(minor / 100);
  }

  function formatDate(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!match) return iso ? String(iso) : "Not available";
    return new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]))));
  }

  function formatStamp(iso) {
    const time = Date.parse(iso || "");
    if (Number.isNaN(time)) return iso ? String(iso) : "Not available";
    return new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Helsinki" }).format(new Date(time));
  }

  function parseAmount(value) {
    const text = String(value ?? "").trim().replace(",", ".");
    if (!/^(?:\d+)(?:\.\d+)?$/.test(text)) return null;
    const number = Number(text);
    return Number.isFinite(number) && number >= 0 ? number : null;
  }

  function parseStyle(brief) {
    const match = /^Requested style: (savory|sweet|not-a-pie)\.\n\n([\s\S]*)$/.exec(brief || "");
    return match ? { style: match[1], brief: match[2] } : { style: "", brief: brief || "" };
  }

  function styleLabel(style) {
    return { savory: "Savory", sweet: "Sweet", "not-a-pie": "Not a pie" }[style] || "Not selected";
  }

  function decimal(value) {
    if (value == null || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function compareNullable(a, b, direction) {
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;
    return (a - b) * direction;
  }

  function rankCandidates(candidates, preference) {
    const list = Array.isArray(candidates) ? candidates.slice() : [];
    if (preference === "price") list.sort((a, b) => compareNullable(decimal(a.purchaseGrossMinor), decimal(b.purchaseGrossMinor), 1));
    else if (preference === "reliability") list.sort((a, b) => compareNullable(decimal(a.reliability), decimal(b.reliability), -1));
    else if (preference === "sustainability") list.sort((a, b) => compareNullable(decimal(a.carbonKgPerKg), decimal(b.carbonKgPerKg), 1));
    return list;
  }

  function hasScope(session, scope) {
    return Array.isArray(session && session.scopes) && session.scopes.includes(scope);
  }

function scopeListKnown(session) {
    return Array.isArray(session && session.scopes);
  }

  function evaluationExpired(job, now) {
    const expiry = job && job.evaluation && job.evaluation.expiresAt;
    const time = Date.parse(expiry || "");
    return !Number.isNaN(time) && time <= now;
  }

  function availableActions(job, session, now) {
    const stateName = job && job.state;
    const expired = evaluationExpired(job, now || Date.now());
    const known = scopeListKnown(session);
    const allow = (scope) => !known || hasScope(session, scope);
    return {
      create: allow("requests:create"),
      approve: stateName === "awaiting_approval" && hasScope(session, "approvals:decide"),
      reject: stateName === "awaiting_approval" && hasScope(session, "approvals:decide"),
      commit: stateName === "ready" && !expired && allow("orders:commit"),
      cancel: Boolean(job) && !STOP_POLL.has(stateName) && allow("requests:cancel"),
      revise: Boolean(job) && allow("requests:create"),
      export: Boolean(job)
    };
  }

  function shouldPoll(state) {
    return !STOP_POLL.has(state);
  }

  function textOf(value) {
    if (typeof value === "string") return value;
    if (value && typeof value === "object") return value.summary || value.message || value.text || value.question || "";
    return "";
  }

  function agentLabel(mode) {
    if (mode === "deterministic") return "Reviewed-recipe planner";
    if (mode === "grok") return "AI planner";
    return mode ? `Planner mode: ${mode}` : "Planner mode not reported";
  }

  function roleLabel(principal) {
    return { chef: "Chef (buyer)", manager: "Kitchen manager", "buyer-agent": "Buyer agent" }[principal] || principal || "Unknown";
  }

  function jobSubtitle(job) {
    const where = job.mode === "live" ? "live Aimo prices and stock" : "demo prices and stock";
    if (job.agentMode === "grok") return `AI interpreted the request; quantities, allergens and limits were checked by code against ${where}.`;
    return `Reviewed recipe, scaled and rounded to pack sizes, then checked against ${where}.`;
  }

  function stockText(quantity) {
    const amount = Number(quantity);
    if (!Number.isFinite(amount)) return "Available";
    if (amount >= 1000000) return "In stock";
    return `${amount} in stock`;
  }

  function formatCutoff(iso) {
    if (!iso) return "";
    const value = new Date(iso);
    if (Number.isNaN(value.getTime())) return "";
    return value.toLocaleString("en-GB", { timeZone: "Europe/Helsinki", weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  }

  function orderNumber(id) {
    return id ? "AIMO-" + String(id).replace(/-/g, "").slice(0, 8).toUpperCase() : "";
  }

  const STEP_MS = 700;
  function pace(ms) {
    const reduced = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    return new Promise((resolve) => setTimeout(resolve, reduced ? 0 : ms));
  }

  function progressList(steps, working) {
    return `<ol class="progress">${steps.map((step) => `<li class="${step.done === false ? "running" : "done"}"><span class="pmark" aria-hidden="true">${step.done === false ? "" : "✓"}</span><span><strong>${esc(step.label)}</strong>${step.detail ? `<span class="pdetail"> · ${esc(step.detail)}</span>` : ""}</span></li>`).join("")}${working ? `<li class="running"><span class="pmark" aria-hidden="true"></span><span>Working…</span></li>` : ""}</ol>`;
  }

  function isWorking(job) {
    if (job.state === "needs_decision") return (job.exceptions || []).length > 0 && job.exceptions.every((item) => item.choice);
    return ["planning", "checking"].includes(job.state);
  }

  function revealing(job) {
    const reveal = state.reveal;
    return Boolean(reveal && reveal.jobId === job.id && !reveal.done);
  }

  function advanceReveal() {
    const reveal = state.reveal;
    const job = state.job;
    if (!reveal || reveal.done || reveal.timer || !job || job.id !== reveal.jobId) return;
    const steps = job.steps || [];
    if (reveal.shown < steps.length) {
      reveal.timer = setTimeout(() => { reveal.timer = 0; reveal.shown += 1; render(); advanceReveal(); }, STEP_MS);
    } else if (!isWorking(job)) {
      reveal.timer = setTimeout(() => { reveal.timer = 0; reveal.done = true; render(); }, 350);
    }
  }

  function startReveal(job, fromCurrent) {
    if (state.reveal && state.reveal.timer) clearTimeout(state.reveal.timer);
    state.reveal = { jobId: job.id, shown: fromCurrent ? (job.steps || []).length : 1, done: false, timer: 0 };
  }

  function placeholderIcon() {
    return `<div class="placeholder" aria-hidden="true">${icon("utensils")}</div>`;
  }

  function stateLabel(state) {
    return {
      planning: "Planning",
      checking: "Checking availability",
      needs_clarification: "Needs more detail",
      needs_decision: "Needs your decision",
      blocked: "Blocked",
      awaiting_approval: "Waiting for approval",
      ready: "Ready to order",
      ordered_mock: "Order placed",
      rejected: "Rejected",
      cancelled: "Cancelled",
      failed: "Failed"
    }[state] || (state ? String(state) : "Not reported");
  }

  function statusClass(state) {
    if (["blocked", "failed", "rejected"].includes(state)) return "status status-bad";
    if (["awaiting_approval", "needs_clarification", "needs_decision", "cancelled"].includes(state)) return "status status-neutral";
    return "status";
  }

  function modeLabel(mode) {
    if (mode === "fixture") return "Demo data";
    if (mode === "live") return "Live Aimo prices and stock";
    return "Evidence mode not reported.";
  }

  function imageChoice(imageUrl, recipeId) {
    const supplied = typeof imageUrl === "string" ? imageUrl.trim() : "";
    if (supplied && !/^(?:javascript|data):/i.test(supplied)) return { src: supplied, illustrative: false, caption: "", credit: "" };
    const known = ILLUSTRATIVE[recipeId];
    return known ? { src: known.file, illustrative: true, caption: known.caption, credit: known.credit } : null;
  }

  function resolveAsset(src, base) {
    if (!src || /^(?:javascript|data):/i.test(src)) return "";
    if (/^https?:\/\//i.test(src) || src.startsWith("/")) return src;
    return new URL(src, base || "./").href;
  }

  function buildJobBody(draft, session) {
    const errors = {};
    const brief = String(draft.brief || "").trim();
    if (!brief) errors.brief = "Describe what you need.";
    if (!draft.style) errors.style = "Choose savory, sweet, or not a pie. This is not inferred from the brief.";
    const servings = Number(draft.servings);
    if (!Number.isInteger(servings) || servings < 1 || servings > 10000) errors.servings = "Enter a whole number of servings from 1 to 10 000.";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.deliveryDate || "")) errors.deliveryDate = "Choose a delivery date.";
    else if (session && session.today && draft.deliveryDate < session.today) errors.deliveryDate = "Choose a date on or after today in Europe/Helsinki.";
    const maxGrossMinor = eurosToMinor(draft.budget);
    if (maxGrossMinor == null) errors.budget = "Enter a goods budget in euros, with at most two decimal places.";
    if (!draft.dietaryConfirmed) errors.dietary = "Confirm the dietary and allergen declaration before submitting.";
    if (!PREFERENCES.some(([value]) => value === draft.preference)) errors.preference = "Choose a ranking preference.";
    const pantry = {};
    const seen = new Set();
    (draft.pantry || []).forEach((row, index) => {
      const key = String(row.key || "").trim();
      const amountText = String(row.amount ?? "").trim();
      if (!key && !amountText) return;
      if (!/^[A-Za-z0-9_-]{1,64}$/.test(key)) errors[`pantry-${index}`] = "Use an ingredient key of letters, numbers, hyphens, or underscores.";
      else if (seen.has(key)) errors[`pantry-${index}`] = "Ingredient keys must be unique.";
      const amount = parseAmount(amountText);
      if (amount == null) errors[`pantry-${index}`] = "Enter a pantry amount of zero or more.";
      if (!errors[`pantry-${index}`]) {
        seen.add(key);
        pantry[key] = amount;
      }
    });
    const styled = draft.style ? `Requested style: ${draft.style}.\n\n${brief}` : brief;
    if (styled.length > 2000) errors.brief = "The brief, including the style line, must be 2 000 characters or fewer.";
    if (Object.keys(errors).length) return { ok: false, errors };
    const body = {
      brief: styled,
      servings,
      deliveryDate: draft.deliveryDate,
      maxGrossMinor,
      dietaryConfirmed: true,
      dietaryRequirements: draft.dietaryRequirements || [],
      excludedAllergens: draft.excludedAllergens || [],
      pantry,
      preference: draft.preference,
      autoCommit: Boolean(draft.autoCommit)
    };
    if (Array.isArray(draft.items) && draft.items.length) body.items = draft.items.map((item) => ({ query: item.query, quantity: String(item.quantity), unit: item.unit }));
    if (session && session.mode === "fixture") body.scenario = draft.scenario || "normal";
    return { ok: true, body, errors: {} };
  }

  function emptyDraft() {
    return {
      brief: "", style: "", servings: "", deliveryDate: "", budget: "", preference: "balanced",
      dietaryConfirmed: false, dietaryRequirements: [], excludedAllergens: [], pantry: [],
      scenario: "normal", autoCommit: true, revisingFrom: null
    };
  }

  const state = {
    phase: "boot",
    session: null,
    jobs: [],
    job: null,
    events: [],
    route: { view: "requests", id: null, tab: "plan" },
    draft: emptyDraft(),
    filter: "",
    rank: "",
    comment: "",
    confirm: "",
    error: "",
    notice: "",
    fieldErrors: {},
    busy: "",
    pollTimer: 0,
    jobSeq: 0,
    lastLive: "",
    ask: "",
    understood: null,
    showForm: false,
    listening: false,
    recognizer: null,
    reveal: null,
    thinking: null,
    placing: null
  };

  function storageGet(key) {
    try { return sessionStorage.getItem(key) || ""; } catch (error) { return ""; }
  }

  function storageSet(key, value) {
    try {
      if (value) sessionStorage.setItem(key, value);
      else sessionStorage.removeItem(key);
    } catch (error) { /* private mode may reject storage; memory still holds the CSRF token */ }
  }

  function csrf() { return state.session && state.session.csrfToken || storageGet(CSRF_KEY); }

  function rememberSession(session) {
    state.session = session;
    if (session && session.csrfToken) storageSet(CSRF_KEY, session.csrfToken);
  }

  function clearAuth() {
    state.session = null;
    state.jobs = [];
    state.job = null;
    storageSet(CSRF_KEY, "");
  }

  async function request(method, path, body, extra) {
    const headers = { Accept: "application/json", ...(extra || {}) };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (method !== "GET" && csrf()) headers["X-CSRF-Token"] = csrf();
    const response = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      cache: "no-store",
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    const type = response.headers.get("content-type") || "";
    let payload = null;
    if (type.includes("json")) payload = await response.json();
    else if (response.status !== 204) payload = await response.text();
    if (!response.ok) {
      const error = new Error(problemText(payload, response.status));
      error.status = response.status;
      error.payload = payload;
      error.retryAfter = response.headers.get("Retry-After");
      throw error;
    }
    return payload;
  }

  function problemText(payload, status) {
    const FRIENDLY = {
      FORBIDDEN: "You don't have permission for this. For example, the total may be above your approval limit.",
      EVALUATION_EXPIRED: "Prices and stock were checked too long ago. Press “Recheck” and try again.",
      EVALUATION_REQUIRED: "Prices or stock changed since the check. Recheck before ordering.",
      RATE_LIMITED: "Too many requests right now. Wait 30 seconds and try again.",
      UPSTREAM_UNAVAILABLE: "Valio Aimo price/stock service is not answering. Try again in a moment."
    };
    if (payload && typeof payload === "object" && FRIENDLY[payload.code]) return FRIENDLY[payload.code];
    if (payload && typeof payload === "object") {
      const detail = payload.detail || payload.title || payload.code || "Request failed";
      return String(detail);
    }
    return status ? `Request failed with status ${status}.` : "Request failed.";
  }

  function parseRoute() {
    const raw = (location.hash || "#requests").replace(/^#\/?/, "");
    const [head, id, tab] = raw.split("/");
    if (head === "job" && id) return { view: "job", id, tab: ["plan", "basket", "comparison", "activity"].includes(tab) ? tab : "basket" };
    if (head === "approvals") return { view: "approvals", id: id || null, tab: "basket" };
    if (head === "orders") return { view: "orders", id: id || null, tab: "basket" };
    return { view: "requests", id: null, tab: "plan" };
  }

  function go(hash) {
    if (location.hash === hash) render();
    else location.hash = hash;
  }

  function assetBase() {
    const script = document.querySelector("script[src$='app.js']");
    return new URL("./", script ? script.src : location.href);
  }

  function announce(text) {
    if (!text || text === state.lastLive) return;
    state.lastLive = text;
    const live = document.getElementById("live");
    if (live) live.textContent = text;
  }

  function captureFocus() {
    const el = document.activeElement;
    if (!el || !el.id || el === document.body) return null;
    return { id: el.id, start: el.selectionStart, end: el.selectionEnd };
  }

  function restoreFocus(saved) {
    if (!saved) return;
    const el = document.getElementById(saved.id);
    if (!el) return;
    el.focus();
    if (typeof saved.start === "number" && el.setSelectionRange) {
      try { el.setSelectionRange(saved.start, saved.end); } catch (error) { /* number inputs */ }
    }
  }

  function syncDraft() {
    const filter = document.getElementById("request-filter");
    if (filter) state.filter = filter.value;
    const comment = document.getElementById("decision-comment");
    if (comment) state.comment = comment.value;
    const rank = document.getElementById("rank-preference");
    if (rank) state.rank = rank.value;
    const form = document.getElementById("request-form");
    if (!form) return;
    const field = (name) => form.elements.namedItem(name);
    state.draft.brief = field("brief").value;
    state.draft.style = field("style").value;
    state.draft.servings = field("servings").value;
    state.draft.deliveryDate = field("deliveryDate").value;
    state.draft.budget = field("budget").value;
    state.draft.preference = field("preference").value;
    state.draft.dietaryConfirmed = field("dietaryConfirmed").checked;
    state.draft.dietaryRequirements = Array.from(form.querySelectorAll("input[name='diet']:checked")).map((node) => node.value);
    state.draft.excludedAllergens = Array.from(form.querySelectorAll("input[name='allergen']:checked")).map((node) => node.value);
    state.draft.autoCommit = field("autoCommit").checked;
    if (field("scenario")) state.draft.scenario = field("scenario").value;
    state.draft.pantry = Array.from(form.querySelectorAll("[data-pantry]")).map((row) => ({
      key: row.querySelector("[data-key]").value,
      amount: row.querySelector("[data-amount]").value
    }));
  }

  function viewSignature() {
    return JSON.stringify({
      phase: state.phase, route: state.route, error: state.error, notice: state.notice, busy: state.busy,
      confirm: state.confirm, filter: state.filter, rank: state.rank, fieldErrors: state.fieldErrors,
      revising: state.draft.revisingFrom, pantry: (state.draft.pantry || []).length,
      jobs: state.jobs.map((job) => [job.id, job.state, job.error, job.order && job.order.id]),
      job: state.job, events: state.events
    });
  }

  function render(options) {
    const signature = viewSignature();
    if (options && options.ifChanged && signature === state.viewSignature) return;
    state.viewSignature = signature;
    const app = document.getElementById("app");
    if (!app) return;
    const focus = captureFocus();
    const y = window.scrollY;
    const previous = app.dataset.route || "";
    const routeKey = `${state.route.view}:${state.route.id || ""}`;
    app.dataset.route = routeKey;
    app.innerHTML = state.phase === "boot" ? shell("<p>Checking the workspace session.</p>")
      : state.phase === "login" ? shell(loginView())
      : shell(workspaceView());
    if (previous && previous !== routeKey) window.scrollTo(0, 0);
    else window.scrollTo(0, y);
    restoreFocus(focus);
    const job = state.job;
    if (job && state.route.view === "job") {
      announce(`${stateLabel(job.state)}.`);
      advanceReveal();
    }
  }

  function shell(main) {
    return `${header()}<main id="main" class="wrap">${banner()}${main}</main>${footer()}`;
  }

  function header() {
    const session = state.session;
    const awaiting = state.jobs.filter((job) => job.state === "awaiting_approval").length;
    const ordered = state.jobs.filter((job) => job.state === "ordered_mock" || job.order).length;
    const current = state.route.view === "job" ? "requests" : state.route.view;
    const link = (view, label, count) => `<a href="#${view}"${current === view ? ' aria-current="page"' : ""}>${esc(label)}${count == null ? "" : ` (${count})`}</a>`;
    const nav = session ? `<nav class="nav" aria-label="Workspace">${link("requests", "Requests")}${link("approvals", "Approvals", awaiting)}${link("orders", "Orders", ordered)}</nav>` : "";
    const tools = session ? `<div class="actions top-actions">
      <button type="button" class="button button-on-teal" data-action="logout">${icon("log-out")} Log out</button>
    </div>` : "";
    const account = session ? `<div class="account"><div class="account-inner"><div class="account-meta">
      <span class="chip">Hotel Aurora Helsinki</span>
      <span>Signed in as <strong>${esc(roleLabel(session.principalId))}</strong></span>
    </div>${nav}</div></div>` : "";
    return `<header><div class="topbar"><div class="topbar-inner"><div class="brand"><p class="wordmark">Aimo</p><p class="brand-sub">Purchasing agent</p></div>
      <div class="top-tools">${tools}</div></div></div>${account}</header>`;
  }

  function footer() {
    return `<footer><div class="wrap credit"><p>Valio Aimo · <a href="icons/LICENSE-lucide.txt">Licences</a></p></div></footer>`;
  }

  function banner() {
    const pending = storageGet(PENDING_KEY);
    const parts = [];
    if (state.error) parts.push(`<div class="alert" role="alert"><p>${esc(state.error)}</p></div>`);
    if (state.notice) parts.push(`<div class="notice"><p>${esc(state.notice)}</p></div>`);
    if (pending && state.phase === "workspace" && state.route.view === "requests") {
      parts.push(`<div class="recovery"><p>A request submission may not have finished. Retry uses the same request key and does not create a duplicate if the server already accepted it.</p><div class="actions"><button type="button" class="button button-secondary" data-action="retry-pending">Retry submission</button><button type="button" class="button button-quiet" data-action="discard-pending">Discard key</button></div></div>`);
    }
    return parts.join("");
  }

  function loginView() {
    return `<section class="login-layout"><h1>Sign in</h1><p>Demo access only. Do not enter a production password.</p>
      <form id="login-form" class="stack" novalidate><div class="field"><label for="login-token">Login token</label><input id="login-token" name="loginToken" type="password" autocomplete="off" spellcheck="false" required></div>
      <button class="button button-primary" type="submit" ${state.busy === "login" ? "disabled" : ""}>${state.busy === "login" ? "Signing in" : "Sign in"}</button></form></section>`;
  }

  function workspaceView() {
    if (state.route.view === "job") return jobView();
    if (state.route.view === "approvals") return listView("Approvals", "Requests waiting for a human decision.", (job) => job.state === "awaiting_approval", "No loaded requests are awaiting approval.");
    if (state.route.view === "orders") return listView("Orders", "Local mock orders only. This is not supplier acceptance or a delivery guarantee.", (job) => job.state === "ordered_mock" || job.order, "No mock orders have been loaded.");
    return requestView();
  }

  const EXAMPLES = [
    "1,000 litres lactose-free milk by Monday",
    "Savory pies for 100 wedding guests on Saturday, under 400 euros",
    "12 litres lactose-free milk for tomorrow"
  ];

  function requestView() {
    const session = state.session;
    const canCreate = availableActions(null, session, Date.now()).create;
    if (!canCreate) {
      return `<section class="stack"><h1>Orders waiting for you</h1>${jobList("Needs your approval", state.jobs.filter((job) => job.state === "awaiting_approval"), "Nothing waiting. You will see orders here when they exceed the buyer's limit.")}<hr class="rule">${jobList("Recent orders", state.jobs.filter((job) => job.state !== "awaiting_approval"), "No orders yet.")}</section>`;
    }
    const body = state.thinking ? `<section class="working-card" aria-live="polite">${progressList(state.thinking, false)}</section>` : state.showForm ? `<div class="stack"><div class="actions-inline"><h2>Order details</h2>${state.understood ? `<button type="button" class="text-link" data-action="hide-form">Back to summary</button>` : ""}</div>${requestForm()}</div>`
      : state.understood ? understoodCard() : examplesBlock();
    return `<section class="stack ask-page">
      <div class="stack-tight"><h1>What do you need?</h1><p class="lead">Type or say it in your own words. The agent finds the products, checks price and delivery, and only asks you when something needs a decision.</p></div>
      ${askBar()}
      ${body}
      <hr class="rule">${jobList("Recent orders", state.jobs, "No orders yet.")}
    </section>`;
  }

  function askBar() {
    const listening = state.listening;
    return `<form id="ask-form" class="ask-bar${listening ? " is-listening" : ""}" novalidate>
      <label class="visually-hidden" for="ask">Your request</label>
      <textarea id="ask" name="ask" rows="2" maxlength="2000" placeholder="e.g. 1,000 litres lactose-free milk by Monday">${esc(state.ask)}</textarea>
      <div class="ask-actions">
        <button type="button" class="mic${listening ? " on" : ""}" data-action="mic" aria-label="${listening ? "Stop listening" : "Speak your request"}" title="${listening ? "Stop listening" : "Speak your request"}">${icon("mic")}<span>${listening ? "Listening…" : "Speak"}</span></button>
        <button type="submit" class="button button-primary" ${state.busy === "interpret" ? "disabled" : ""}>${state.busy === "interpret" ? "Reading…" : "Continue"}</button>
      </div>
    </form>
    ${state.showForm ? "" : `<button type="button" class="text-link" data-action="show-form">Use the order form instead</button>`}`;
  }

  function examplesBlock() {
    return `<div class="examples"><p class="label">Try</p>${EXAMPLES.map((text) => `<button type="button" class="example" data-action="example" data-text="${esc(text)}">${esc(text)}</button>`).join("")}</div>`;
  }

  const FIELD_LABELS = { items: "Products", style: "Pie style", servings: "Guests", deliveryDate: "Delivery", budget: "Budget", dietaryRequirements: "Diet", excludedAllergens: "Allergies", preference: "Priority" };

  function chipValue(name, field) {
    const value = field.value;
    if (name === "items") return (value || []).map((item) => `${formatQuantity(item.quantity)} ${item.unit === "l" ? "L" : item.unit} ${item.query}`).join(", ");
    if (name === "deliveryDate") return value ? formatDay(value) : "";
    if (name === "budget") return value ? `up to ${formatMinor(eurosToMinor(value))}` : "";
    if (name === "dietaryRequirements") return (value || []).length ? value.map((key) => (DIET.find(([k]) => k === key) || [key, key])[1].replace(" (not milk-free)", "")).join(", ") : "None";
    if (name === "excludedAllergens") return (value || []).length ? "No " + value.map((key) => (ALLERGENS.find(([k]) => k === key) || [key, key])[1].toLowerCase()).join(", no ") : "None";
    if (name === "preference") return (PREFERENCES.find(([k]) => k === value) || [value, value])[1];
    if (name === "style") return styleLabel(value);
    return value == null ? "" : String(value);
  }

  function understoodCard() {
    const result = state.understood;
    const fields = result.fields || {};
    const order = result.kind === "recipe" ? ["style", "servings", "deliveryDate", "budget", "excludedAllergens", "dietaryRequirements", "preference"]
      : ["items", "deliveryDate", "budget", "dietaryRequirements", "excludedAllergens", "preference"];
    const chips = order.filter((name) => fields[name] && fields[name].source !== "missing").map((name) => {
      const field = fields[name];
      const check = field.source === "inferred" || field.source === "default";
      const note = field.note ? ` · ${field.note}` : field.source === "inferred" && field.evidence ? ` · from “${field.evidence}”` : "";
      return `<button type="button" class="uchip${check ? " uchip-check" : ""}" data-action="show-form" title="${check ? "Assumed. Tap to change." : "From your request. Tap to change."}"><span class="uchip-label">${esc(FIELD_LABELS[name])}</span><span class="uchip-value">${esc(chipValue(name, field))}</span>${check ? `<span class="uchip-note">${esc(field.source === "default" ? "assumed" : "check")}${esc(note)}</span>` : ""}</button>`;
    }).join("");
    const questions = (result.questions || []).map((item) => `<div class="question"><p><strong>${esc(item.question)}</strong></p><div class="actions-inline">${(item.options || []).length
      ? item.options.map((option) => `<button type="button" class="button button-secondary" data-action="answer" data-field="${esc(item.field)}" data-value="${esc(option)}">${esc(styleLabel(option) || option)}</button>`).join("")
      : item.field === "servings" ? `<input id="answer-servings" inputmode="numeric" aria-label="Number of guests" placeholder="100"><button type="button" class="button button-secondary" data-action="answer" data-field="servings">Set</button>` : ""}</div></div>`).join("");
    const limit = state.session && state.session.policy && state.session.policy.autonomousLimitMinor;
    const ready = !(result.questions || []).length;
    return `<section class="understood" aria-label="What the agent understood">
      <div class="actions-inline"><h2>Here's what I understood</h2><button type="button" class="text-link" data-action="show-form">${icon("pencil")} Edit details</button></div>
      <div class="uchips">${chips}</div>
      ${questions}
      ${ready ? `<div class="check confirm-diet"><input id="dietaryConfirmed" type="checkbox" ${state.draft.dietaryConfirmed ? "checked" : ""} data-bind="dietaryConfirmed"><label for="dietaryConfirmed">Diet and allergies above are correct</label></div>
      <div class="check"><input id="autoCommit" type="checkbox" ${state.draft.autoCommit ? "checked" : ""} data-bind="autoCommit"><label for="autoCommit">Order automatically if the total stays under ${esc(formatMinor(limit))}</label></div>
      <button type="button" class="button button-primary button-big" data-action="find" ${state.busy === "submit" || !state.draft.dietaryConfirmed ? "disabled" : ""}>${state.busy === "submit" ? "Starting…" : "Find products"}</button>${state.draft.dietaryConfirmed ? "" : `<p class="hint">Tick the diet confirmation to continue.</p>`}` : ""}
    </section>`;
  }

  function formatQuantity(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toLocaleString("en-GB", { maximumFractionDigits: 2 }) : String(value);
  }

  function formatDay(iso) {
    if (!iso) return "";
    const date = new Date(`${iso}T12:00:00`);
    return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
  }

  function requestForm() {
    const draft = state.draft;
    const errors = state.fieldErrors;
    const session = state.session;
    const today = session && session.today;
    const fixture = session && session.mode === "fixture";
    const policy = session && session.policy || {};
    const limits = Number.isInteger(policy.autonomousLimitMinor) || Number.isInteger(policy.orderLimitMinor)
      ? `You can order up to ${formatMinor(policy.autonomousLimitMinor)} without approval. Larger baskets go to a manager (max ${formatMinor(policy.orderLimitMinor)} per order).`
      : "Delegated limits were not returned with the session.";
    return `<form id="request-form" class="stack" novalidate>
      ${draft.revisingFrom ? `<div class="notice"><p>This starts a new request. Approval of ${esc(draft.revisingFrom)} will not apply.</p></div>` : ""}
      <div class="actions"><button type="button" class="button button-quiet" data-action="fill-wedding">Fill savory wedding-pie example</button><button type="button" class="button button-quiet" data-action="fill-milk">Fill lactose-free milk example</button></div>
      <div class="field field-wide"><label for="brief">What do you need?</label><textarea id="brief" name="brief" maxlength="1900" placeholder="Vegetable pies for 100 wedding guests">${esc(draft.brief)}</textarea>${fieldError("brief")}</div>
      <div class="fields">
        <div class="field"><label for="style">Style</label><select id="style" name="style"><option value="">Choose</option><option value="savory" ${draft.style === "savory" ? "selected" : ""}>Savory</option><option value="sweet" ${draft.style === "sweet" ? "selected" : ""}>Sweet</option><option value="not-a-pie" ${draft.style === "not-a-pie" ? "selected" : ""}>Not a pie</option></select>${fieldError("style")}</div>
        <div class="field"><label for="servings">Servings</label><div class="stepper"><button type="button" class="icon-button" data-action="step" data-target="servings" data-delta="-1" data-tooltip="Decrease servings" title="Decrease servings" aria-label="Decrease servings">${icon("minus")}</button><input id="servings" name="servings" inputmode="numeric" value="${esc(draft.servings)}"><button type="button" class="icon-button" data-action="step" data-target="servings" data-delta="1" data-tooltip="Increase servings" title="Increase servings" aria-label="Increase servings">${icon("plus")}</button></div>${fieldError("servings")}</div>
        <div class="field"><label for="deliveryDate">Delivery date</label><input id="deliveryDate" name="deliveryDate" type="date" ${today ? `min="${esc(today)}"` : ""} value="${esc(draft.deliveryDate)}">${fieldError("deliveryDate")}<p class="hint">${today ? `Today in Europe/Helsinki is ${esc(formatDate(today))}.` : "Helsinki today was not returned; the server will reject a past date."}</p></div>
        <div class="field"><label for="budget">Goods budget, VAT included (EUR)</label><input id="budget" name="budget" inputmode="decimal" value="${esc(draft.budget)}" autocomplete="off">${fieldError("budget")}<p class="hint">Delivery and payment charges are not included.</p></div>
        <div class="field"><label for="preference">Ranking preference</label><select id="preference" name="preference">${PREFERENCES.map(([value, label]) => `<option value="${value}" ${draft.preference === value ? "selected" : ""}>${label}</option>`).join("")}</select><p class="hint">${esc(PREFERENCES.find(([value]) => value === draft.preference)[2])}</p></div>
        ${fixture ? `<div class="field"><label for="scenario">Fixture scenario</label><select id="scenario" name="scenario"><option value="normal" ${draft.scenario === "normal" ? "selected" : ""}>Normal</option><option value="shortage" ${draft.scenario === "shortage" ? "selected" : ""}>Stock shortage</option><option value="late" ${draft.scenario === "late" ? "selected" : ""}>Late date</option></select><p class="hint">Demo-only stock/date problem to show recovery.</p></div>` : ""}
      </div>
      <fieldset class="stack"><legend class="label">Dietary requirements</legend><div class="checks">${DIET.map(([value, label]) => check("diet", value, label, draft.dietaryRequirements.includes(value))).join("")}</div></fieldset>
      <details class="constraint-details" ${draft.excludedAllergens.length ? "open" : ""}><summary>Excluded allergens (${draft.excludedAllergens.length})</summary><fieldset class="stack"><legend class="visually-hidden">Excluded allergens</legend><div class="checks">${ALLERGENS.map(([value, label]) => check("allergen", value, label, draft.excludedAllergens.includes(value))).join("")}</div><p class="hint">Unknown evidence blocks the affected purchase.</p></fieldset></details>
      <div class="check"><input id="dietaryConfirmed" name="dietaryConfirmed" type="checkbox" ${draft.dietaryConfirmed ? "checked" : ""}><label for="dietaryConfirmed">Dietary needs and allergens above are correct (nothing ticked = no restrictions).</label></div>
      ${fieldError("dietary")}
      <details class="more-options" ${state.moreOpen || (draft.pantry || []).length || draft.autoCommit ? "open" : ""}><summary>More options: pantry stock, auto-order, recipes</summary><div class="stack">
      <div class="stack-tight"><div class="actions"><h2>Pantry</h2><button type="button" class="button button-quiet" data-action="add-pantry">${icon("plus")} Add pantry row</button></div>
        <p class="hint">Already in your kitchen? Enter the ingredient (e.g. flour) and amount in the recipe unit; it is subtracted from the order.</p>
        ${(draft.pantry || []).map((row, index) => `<div class="pantry-row" data-pantry><label class="visually-hidden" for="pantry-key-${index}">Ingredient key</label><input id="pantry-key-${index}" data-key type="text" value="${esc(row.key)}" autocomplete="off"><label class="visually-hidden" for="pantry-amount-${index}">Amount</label><input id="pantry-amount-${index}" data-amount inputmode="decimal" value="${esc(row.amount)}">${iconButton("trash-2", "remove-pantry", "Remove pantry row", `data-index="${index}"`)}${fieldError(`pantry-${index}`)}</div>`).join("")}
      </div>
      <div class="check"><input id="autoCommit" name="autoCommit" type="checkbox" ${draft.autoCommit ? "checked" : ""}><label for="autoCommit">Order automatically when the basket is within my limit.</label></div>
      <details class="recipe-details"><summary>Recipe library</summary>${recipesBlock()}</details>
      </div></details>
      <p class="hint">${esc(limits)}</p>
      <button class="button button-primary" type="submit" ${state.busy === "submit" ? "disabled" : ""}>${state.busy === "submit" ? "Submitting request" : "Submit request"}</button>
    </form>`;
  }

  function check(name, value, label, checked) {
    const id = `${name}-${value}`;
    return `<div class="check"><input id="${id}" name="${name}" type="checkbox" value="${value}" ${checked ? "checked" : ""}><label for="${id}">${esc(label)}</label></div>`;
  }

  function fieldError(name) {
    const message = state.fieldErrors[name];
    return message ? `<p class="hint" id="${name}-error" role="alert">${esc(message)}</p>` : "";
  }

  function recipesBlock() {
    const recipes = state.session && state.session.recipes;
    if (!Array.isArray(recipes) || !recipes.length) return `<p class="hint">No curated recipes were returned with this session.</p>`;
    return `<div class="stack"><h2>Curated recipes</h2><div class="list recipe-library">${recipes.map((recipe) => {
      const image = imageChoice(recipe.imageUrl, recipe.id);
      return `<article class="ingredient"><div>${image ? photo(image, recipe.title || recipe.id) : `<div class="placeholder">No recipe image supplied</div>`}<h3 class="wrap-text">${esc(recipe.title || recipe.id || "Untitled recipe")}</h3><p class="meta">${esc(recipe.id || "No id")} · ${recipe.servings == null ? "Servings not supplied" : `${esc(recipe.servings)} servings`}</p></div><div class="actions"><button type="button" class="button button-quiet" data-action="use-recipe" data-id="${esc(recipe.id || "")}">Use title and servings</button></div></article>`;
    }).join("")}</div></div>`;
  }

  function photo(image, alt) {
    const src = resolveAsset(image.src, assetBase().href);
    if (!src) return `<div class="placeholder">Image unavailable</div>`;
    return `<figure class="stack-tight"><img class="recipe-photo" src="${esc(src)}" alt="${esc(image.illustrative ? image.caption : alt || "Supplied recipe image")}" referrerpolicy="no-referrer">${image.illustrative ? `<figcaption class="credit">${esc(image.caption)} ${esc(image.credit)}.</figcaption>` : ""}</figure>`;
  }

  function listView(title, intro, predicate, empty) {
    return `<section class="stack"><div class="stack-tight"><h1>${esc(title)}</h1><p>${esc(intro)}</p></div>${jobList(title, state.jobs.filter(predicate), empty)}</section>`;
  }

  function jobList(title, jobs, empty) {
    const query = state.filter.trim().toLowerCase();
    const visible = jobs.filter((job) => !query || `${job.brief || ""} ${job.id || ""} ${job.state || ""}`.toLowerCase().includes(query));
    const rows = visible.map((job) => `<a class="job-row" href="#job/${esc(job.id)}/basket"><span class="wrap-text"><strong>${esc(jobTitle(job))}</strong><br><span class="meta">Delivery ${esc(formatDay(job.deliveryDate))}${job.order && job.order.totals ? ` · ${formatMinor(job.order.totals.grossMinor)}` : job.evaluation && job.evaluation.totals ? ` · ${formatMinor(job.evaluation.totals.grossMinor)}` : ""}</span></span><span class="${statusClass(job.state)}">${esc(stateLabel(job.state))}</span><span class="meta">${esc(formatStamp(job.createdAt))}</span></a>`).join("");
    const filter = jobs.length > 5 ? `<div class="field"><label for="request-filter">Search orders</label><input id="request-filter" value="${esc(state.filter)}" autocomplete="off"></div>` : "";
    return `<section class="stack">${filter}<h2>${esc(title)}</h2>${rows || `<p>${esc(empty)}</p>`}</section>`;
  }

  function jobView() {
    const job = state.job;
    if (!job) return `<section class="stack"><h1>Order</h1><p>${state.busy === "job" ? "Loading…" : "This order is not loaded."}</p></section>`;
    const actions = availableActions(job, state.session, Date.now());
    return `<section class="job-layout">
      <div class="stack">
        <div class="stack-tight"><a class="text-link back" href="#requests">← New request</a>
          <p class="${revealing(job) || isWorking(job) ? "status" : statusClass(job.state)}">${esc(revealing(job) || isWorking(job) ? "Working…" : stateLabel(job.state))}</p>
          <h1 class="wrap-text">${esc(jobTitle(job))}</h1>
          <p class="meta">${esc(orderMeta(job))}</p></div>
        ${stepper(job)}
        ${revealing(job) || isWorking(job) ? `<section class="working-card" aria-live="polite"><h2>Working on it</h2>${progressList((job.steps || []).slice(0, revealing(job) ? state.reveal.shown : undefined), true)}</section>`
          : `${exceptionCards(job)}${basketBlock(job)}${stepsSummary(job)}${agentLog(job)}`}
        ${job.plan && job.plan.recipeId ? `<details class="more"><summary>Recipe and quantities</summary>${planPanel(job)}</details>` : ""}
        <details class="more"><summary>Compare alternatives</summary>${comparisonPanel(job)}</details>
        <details class="more"><summary>${icon("history")} Order record</summary>${activityPanel(job)}</details>
      </div>
      <aside class="decision" aria-label="Decision">${revealing(job) || isWorking(job) ? `<h2>Decision</h2><p>The agent is checking products. Nothing is ordered yet.</p>` : decision(job, actions)}</aside></section>`;
  }

  function jobTitle(job) {
    const brief = parseStyle(job.brief || "").brief || job.brief || "Order";
    if (job.plan && job.plan.recipeId) return job.plan.title;
    return brief.charAt(0).toUpperCase() + brief.slice(1);
  }

  function orderMeta(job) {
    const parts = [`Delivery ${formatDay(job.deliveryDate)}`];
    if (Number.isInteger(job.maxGrossMinor)) parts.push(`budget ${formatMinor(job.maxGrossMinor)}`);
    if ((job.dietaryRequirements || []).length) parts.push(job.dietaryRequirements.map((key) => (DIET.find(([k]) => k === key) || [key, key])[1].replace(" (not milk-free)", "")).join(", "));
    if ((job.excludedAllergens || []).length) parts.push("no " + job.excludedAllergens.join(", no ").replaceAll("_", " "));
    return parts.join(" · ");
  }

  function stepper(job) {
    const s = revealing(job) && !state.reveal.resolving ? "checking" : revealing(job) ? "planning-order" : job.state;
    const looked = !["planning"].includes(s) && !(s === "checking" && !job.plan);
    const ordered = s !== "checking" && (Boolean(job.evaluation) || ["awaiting_approval", "ready", "ordered_mock"].includes(s));
    const steps = [
      ["Request", "done"],
      ["Lookup", looked ? "done" : "active"],
      [s === "needs_decision" ? "Your decision" : "Order", s === "needs_decision" || s === "planning-order" ? "active" : ordered ? "done" : ""],
      ["Approval", s === "ordered_mock" ? "done" : s === "awaiting_approval" || s === "ready" ? "active" : ""]
    ];
    if (["blocked", "failed", "rejected", "cancelled", "needs_clarification"].includes(s)) steps[ordered ? 3 : 2][1] = "stopped";
    return `<ol class="stepper-flow">${steps.map(([label, status], index) => `<li class="${status}"><span class="dot">${status === "done" ? "✓" : index + 1}</span>${esc(label)}</li>`).join("")}</ol>`;
  }

  function exceptionCards(job) {
    const items = job.exceptions || [];
    const canAnswer = availableActions(null, state.session, Date.now()).create;
    const open = items.filter((item) => !item.choice);
    if (!open.length) return "";
    return open.map((item) => `<article class="xcard ${item.severity === "blocked" ? "xcard-blocked" : ""}" aria-label="Decision needed">
      <p class="xkind">${icon("circle-alert")} ${item.severity === "blocked" ? "Can't be ordered" : "Your decision"}</p>
      <h2>${esc(item.title)}</h2>
      <p>${esc(item.detail)}</p>
      ${item.options && item.options.length ? (canAnswer && job.state === "needs_decision" ? `<div class="xoptions">${item.options.map((option) => `<button type="button" class="xoption ${option.primary ? "recommended" : ""}" data-action="resolve" data-exception="${esc(item.id)}" data-option="${esc(option.id)}" ${state.busy ? "disabled" : ""}>
        <span class="xlabel">${option.primary ? '<span class="tag">Recommended</span>' : ""}${esc(option.label)}</span><span class="xeffect">${esc(option.effect || "")}</span></button>`).join("")}</div>`
        : `<p class="hint">Waiting for the buyer's decision.</p>`) : `<div class="actions-inline"><button type="button" class="button button-secondary" data-action="revise">${icon("pencil")} Change the request</button></div>`}
    </article>`).join("");
  }

  function basketBlock(job) {
    const order = job.order;
    const evaluation = job.evaluation;
    const lines = (order && order.lines) || (evaluation && evaluation.lines) || [];
    const body = lines.length ? lines.map((line) => productRow(line, job)).join("") : proposedRows(job);
    if (!body) return job.state === "planning" || job.state === "checking" ? `<p class="working">${icon("search")} Finding products and checking live price and stock…</p>` : "";
    const totals = (order || evaluation || {}).totals;
    return `<section class="stack-tight basket"><div class="actions-inline"><h2>${order ? "Ordered" : evaluation ? "Basket" : "Proposed basket"}</h2>${totals ? `<p class="basket-total">${formatMinor(totals.grossMinor)} <span class="hint">incl. VAT</span></p>` : ""}</div>
      <div class="list">${body}</div>
      ${evaluation && !order ? `<p class="hint">Price and stock checked ${esc(formatStamp(evaluation.checkedAt))} · checked again before ordering.</p>` : ""}</section>`;
  }

  function stepsSummary(job) {
    const steps = job.steps || [];
    if (!steps.length) return "";
    return `<details class="more steps-summary"><summary>✓ ${steps.length} checks done · ${esc(steps.map((step) => step.label.toLowerCase()).slice(1, 4).join(" · "))}</summary>${progressList(steps, false)}</details>`;
  }

  function agentLog(job) {
    const plan = job.plan || {};
    let lines = (plan.explanations || []).map(textOf).filter((text) => text && !/^Deterministic|^The planner|^Reliability is|^Candidates compared|^Live comparison/.test(text) && !/ chose: /.test(text));
    const skipped = lines.filter((text) => text.startsWith("Skipped "));
    if (skipped.length > 2) {
      const reasons = {};
      skipped.forEach((text) => { const why = (text.split(" — ")[1] || "not orderable").replace(/ \(.*\)$/, ""); reasons[why] = (reasons[why] || 0) + 1; });
      lines = [`Skipped ${skipped.length} products — ${Object.entries(reasons).map(([why, count]) => `${why} (${count})`).join(", ")}. See Compare alternatives.`, ...lines.filter((text) => !text.startsWith("Skipped "))];
    }
    const progress = (job.messages || []).map(textOf).filter(Boolean);
    if (!lines.length && !progress.length) return "";
    return `<details class="more agent-log" open><summary>What happened and why</summary><div class="log-cols"><div><p class="label">Agent decisions</p><ul>${lines.map((text) => `<li>${esc(text)}</li>`).join("") || "<li class=\"hint\">No choices needed.</li>"}</ul></div><div><p class="label">Timeline</p><ol class="timeline">${progress.map((text) => `<li>${esc(text)}</li>`).join("")}</ol></div></div></details>`;
  }

  function requestFacts(job) {
    const parsed = parseStyle(job.brief);
    const rows = [
      ["Brief", parsed.brief || job.brief || "Not supplied"],
      ["Style", parsed.style ? styleLabel(parsed.style) : "Not separately recorded"],
      ["Servings", job.servings == null ? "Not supplied" : String(job.servings)],
      ["Delivery date", formatDate(job.deliveryDate)],
      ["Goods budget", formatMinor(job.maxGrossMinor)],
      ["Preference", job.preference || "Not supplied"],
    ];
    if (job.autoCommit) rows.push(["Auto-order", "Within my limit"]);
    if (job.mode === "fixture" && job.scenario && job.scenario !== "normal") rows.push(["Demo scenario", job.scenario]);
    if (Array.isArray(job.dietaryRequirements)) rows.push(["Dietary requirements", job.dietaryRequirements.join(", ") || "None declared"]);
    if (Array.isArray(job.excludedAllergens)) rows.push(["Excluded allergens", job.excludedAllergens.join(", ") || "None declared"]);
    return `<dl class="facts">${rows.map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join("")}</dl>`;
  }

  function panel(job) {
    if (state.route.tab === "basket") return basketPanel(job);
    if (state.route.tab === "comparison") return comparisonPanel(job);
    if (state.route.tab === "activity") return activityPanel(job);
    return planPanel(job);
  }

  function planPanel(job) {
    const plan = job.plan;
    if (!plan) return `<p>${job.state === "planning" || job.state === "checking" ? "The plan has not been returned yet." : "No plan was returned."}</p>${messages(job)}`;
    const image = imageChoice(plan.imageUrl, plan.recipeId);
    const questions = (plan.questions || []).map(textOf).filter(Boolean);
    const warnings = (plan.warnings || []).map(textOf).filter(Boolean);
    const explanations = (plan.explanations || []).map(textOf).filter(Boolean);
    return `<div class="stack">${image ? photo(image, plan.title) : `<div class="placeholder">No recipe image supplied</div>`}
      <dl class="facts"><dt>Recipe</dt><dd>${esc(plan.title || "Not named")}</dd><dt>Recipe id</dt><dd class="mono">${esc(plan.recipeId || "Not supplied")}</dd><dt>Source</dt><dd>${esc(plan.recipeSource || "Not supplied")}</dd><dt>Yield</dt><dd>${plan.servings == null ? "Not supplied" : `${esc(plan.servings)} servings`}</dd></dl>
      ${questions.length ? `<div class="alert"><h2>Clarification</h2>${questions.map((item) => `<p>${esc(item)}</p>`).join("")}</div>` : ""}
      ${warnings.map((item) => `<p class="notice">${esc(item)}</p>`).join("")}
      ${explanations.length ? `<details class="explain"><summary>How this was calculated</summary>${explanations.map((item) => `<p>${esc(item)}</p>`).join("")}</details>` : ""}
      <h2>Ingredient calculation</h2>
      <div class="list">${(plan.ingredients || []).map(ingredientRow).join("") || "<p>No ingredient rows were returned.</p>"}</div>
      ${messages(job)}</div>`;
  }

  function ingredientRow(item) {
    return `<article class="ingredient"><div><h3 class="wrap-text">${esc(item.label || item.key || "Ingredient")}</h3><p class="meta mono">${esc(item.key || "")}</p></div>
      <p>Required ${esc(item.required ?? "—")} ${esc(item.unit || "")}<br>Pantry ${esc(item.pantry ?? "—")}<br>Needed ${esc(item.needed ?? "—")}</p>
      <p>Product <span class="mono">${esc(item.productId || "None selected")}</span><br>${esc(item.quantity ?? "—")} × ${esc(item.packAmount ?? "—")} ${esc(item.unit || "")}<br>Overage ${esc(item.overage ?? "—")}</p></article>`;
  }

  function basketPanel(job) {
    const order = job.order;
    const evaluation = job.evaluation;
    const lines = (order && order.lines) || (evaluation && evaluation.lines) || [];
    const source = order ? "Ordered basket" : evaluation ? "Checked basket" : "Proposed basket";
    const body = lines.length ? lines.map((line) => productRow(line, job)).join("") : proposedRows(job);
    return `<div class="stack"><p>${esc(source)} · ${esc(modeLabel((evaluation && evaluation.mode) || job.mode))} · ${lines.length || (job.plan && job.plan.lines || []).length} products</p>
      <p class="hint">Prices and stock checked ${esc(formatStamp(evaluation && evaluation.checkedAt))}, valid until ${esc(formatStamp(evaluation && evaluation.expiresAt))}. Checking does not reserve stock.</p>
      ${totalsBlock(order || evaluation, job)}
      <div class="list">${body || "<p>No basket lines have been returned.</p>"}</div>
      ${reasonsBlock(evaluation && evaluation.reasons)}</div>`;
  }

  function proposedRows(job) {
    const lines = job.plan && job.plan.lines || [];
    return lines.map((line) => {
      const ingredient = (job.plan.ingredients || []).find((item) => item.productId === line.productId) || {};
      const candidate = (ingredient.candidates || []).find((item) => item.productId === line.productId) || {};
      return productRow({ ...candidate, ...line, name: candidate.name || ingredient.label }, job);
    }).join("");
  }

  function productRow(line, job) {
    const meta = candidateFor(job, line.productId);
    const image = meta && meta.imageUrl ? resolveAsset(meta.imageUrl, assetBase().href) : "";
    const pricing = line.pricing;
    const availability = line.availability;
    const ingredient = ((job.plan && job.plan.ingredients) || []).filter((item) => item.productId === line.productId);
    const calc = ingredient.map((item) => `For ${String(item.label || item.key).toLowerCase()}: need ${item.needed ?? "—"} ${item.unit || ""}${Number(item.overage) > 0 ? `, ${item.overage} ${item.unit || ""} extra from pack size` : ""}`).join("; ");
    return `<article class="product-row"><div>${image ? `<img class="thumb" src="${esc(image)}" alt="" referrerpolicy="no-referrer">` : placeholderIcon()}</div>
      <div><h3 class="product-name">${esc(line.name || meta && meta.name || "Product")}</h3><p class="meta mono">${esc(line.productId || "")}${meta && meta.reliability != null ? ` · delivered in full ${Math.round(meta.reliability * 100)} %` : ""}</p>${meta && (meta.labels || []).filter((label) => !/_|Temperature/.test(label)).length ? `<p class="badges">${meta.labels.filter((label) => !/_|Temperature/.test(label)).map((label) => `<span class="badge">${esc(label)}</span>`).join("")}</p>` : ""}${calc ? `<p>${esc(calc)}</p>` : ""}${line.reasons && line.reasons.length ? `<p>${line.reasons.map((reason) => esc(reason.message || reasonLabel(reason.code))).join(" ")}</p>` : ""}</div>
      <div class="qty"><p class="label">Quantity</p><p class="mono">${esc(line.quantity == null ? "—" : formatQuantity(line.quantity))}${meta && meta.unit && meta.packAmount ? ` × ${esc(formatQuantity(meta.packAmount))} ${esc(meta.unit)}` : ""}</p><p class="hint"><span class="stock${availability && availability.quantityConfirmed && Number(availability.availableQuantity) <= Number(line.quantity) ? " low" : ""}${!availability ? " none" : ""}">${availabilityText(availability)}</span></p></div>
      <div class="total"><p class="label">Line total</p><p class="mono">${pricing ? formatMinor(pricing.grossMinor) : "Not available"}</p><p class="hint">${pricing ? `€${esc(Number(pricing.unitGross).toFixed(2))} each incl. VAT` : "Price missing, so it is not counted as zero."}</p></div></article>`;
  }

  function candidateFor(job, productId) {
    const ingredients = job.plan && job.plan.ingredients || [];
    for (const item of ingredients) {
      const found = (item.candidates || []).find((candidate) => candidate.productId === productId);
      if (found) return found;
    }
    return null;
  }

  function availabilityText(availability) {
    if (!availability) return "Delivery result not checked.";
    if (availability.quantityConfirmed === false || availability.logisticModel === "Terminal" || availability.logisticModel === "Unknown") return "Stock quantity not confirmed by Aimo.";
    const date = availability.availableDate ? formatDate(availability.availableDate) : "date not supplied";
    const cutoff = availability.closingTime ? formatStamp(availability.closingTime) : "cutoff not supplied";
    return `${stockText(availability.availableQuantity)} · order by ${formatCutoff(availability.closingTime) || cutoff}`;
  }

  function totalsBlock(source, job) {
    const totals = source && source.totals;
    if (!totals) return `<p>No complete goods total. Missing prices are not shown as zero.</p>`;
    const servings = Number(job.servings);
    const perServing = Number.isInteger(totals.grossMinor) && Number.isInteger(servings) && servings > 0 ? formatMinor(Math.round(totals.grossMinor / servings)) : "Not available";
    const budget = Number.isInteger(job.maxGrossMinor) && Number.isInteger(totals.grossMinor) ? formatMinor(job.maxGrossMinor - totals.grossMinor) : "Not available";
    return `<dl class="totals"><dt>Net goods</dt><dd>${formatMinor(totals.netMinor)}</dd><dt>VAT</dt><dd>${formatMinor(totals.taxMinor)}</dd><dt>Gross goods</dt><dd>${formatMinor(totals.grossMinor)}</dd><dt>Basis</dt><dd>${totals.basis === "goods_only" ? "Goods only, VAT included" : esc(totals.basis || "Not supplied")}</dd><dt>Budget remainder</dt><dd>${budget}</dd><dt>Per serving</dt><dd>${perServing}</dd></dl><p class="hint">Per serving is display rounding of the gross goods total. Delivery and payment charges are not included.</p>`;
  }

  function comparisonPanel(job) {
    const plan = job.plan;
    if (!plan || !(plan.ingredients || []).length) return `<p class="hint">Alternatives appear after the lookup.</p>`;
    const chosen = new Set(((job.order || job.evaluation || {}).lines || plan.lines || []).map((line) => line.productId));
    return `<div class="stack">${plan.ingredients.map((item) => {
      const rows = (item.candidates || []).map((candidate) => {
        const inBasket = chosen.has(candidate.productId);
        const skipped = candidate.available === false;
        const why = skipped ? (candidate.reasons || []).map((reason) => SHORT_REASONS[reason.code] || reasonLabel(reason.code))[0] || "Not orderable" : "";
        const price = candidate.perUnitGross ? `€${String(candidate.perUnitGross)} / ${candidate.unit || "unit"}` : candidate.purchaseGrossMinor != null ? formatMinor(candidate.purchaseGrossMinor) : "—";
        return { inBasket, skipped, sortPrice: Number(candidate.perUnitGross || candidate.purchaseGrossMinor || 1e9), html: `<tr class="${inBasket ? "chosen" : skipped ? "skipped" : ""}">
          <td><strong>${esc(candidate.name || candidate.productId)}</strong>${(candidate.labels || []).filter((label) => !/_|Temperature/.test(label)).length ? `<br><span class="badges">${candidate.labels.filter((label) => !/_|Temperature/.test(label)).map((label) => `<span class="badge">${esc(label)}</span>`).join("")}</span>` : ""}</td>
          <td class="num">${esc(price)}</td>
          <td>${candidate.stockAmount ? `${esc(formatQuantity(candidate.stockAmount))} ${esc(candidate.unit || "")}` : skipped ? "—" : "In stock"}</td>
          <td class="num">${candidate.reliability == null ? "—" : `${Math.round(candidate.reliability * 100)} %`}</td>
          <td>${inBasket ? "<strong>In basket</strong>" : skipped ? esc(why) : "Alternative"}</td></tr>` };
      }).sort((a, b) => (b.inBasket - a.inBasket) || (a.skipped - b.skipped) || (a.sortPrice - b.sortPrice));
      return `<section class="stack-tight"><h3>${esc(item.label || item.key)}</h3><div class="table-wrap"><table class="compare"><thead><tr><th>Product</th><th class="num">Price</th><th>Stock</th><th class="num">Delivered in full</th><th>Status</th></tr></thead><tbody>${rows.map((row) => row.html).join("")}</tbody></table></div></section>`;
    }).join("")}<p class="hint">Delivered in full = share of past orders delivered completely (Valio Aimo history).</p></div>`;
  }

  const SHORT_REASONS = {
    CUTOFF_PASSED: "Cutoff passed",
    DELIVERY_UNAVAILABLE: "Not available",
    QUANTITY_UNCONFIRMED: "Stock unconfirmed",
    SALES_BLOCK: "Sales blocked",
    DIETARY_CONFLICT: "Fails diet",
    DIETARY_UNCONFIRMED: "Diet info missing",
    PRICE_UNAVAILABLE: "No price",
    DELIVERY_DATE_MISMATCH: "Wrong day",
    INSUFFICIENT_STOCK: "Not enough stock"
  };

  function activityPanel(job) {
    const events = Array.isArray(state.events) ? state.events : [];
    return `<div class="stack"><p class="hint">Every action by the buyer, the agent and the kitchen manager, as recorded by the ordering gateway.</p>${events.length ? `<div class="list">${events.map(eventRow).join("")}</div>` : "<p>No audit events have been loaded.</p>"}</div>`;
  }

  function messages(job) {
    const items = (job.messages || []).map(textOf).filter(Boolean);
    if (!items.length && !job.error) return "";
    return `<section class="stack-tight"><h2>Workspace updates</h2>${items.map((item) => `<p>${esc(item)}</p>`).join("")}${job.error ? `<p class="alert" role="alert">${esc(job.error)}</p>` : ""}</section>`;
  }

  function eventRow(event) {
    const label = {
      "request.created": "Request created",
      "request.cancelled": "Request cancelled",
      "basket.created": "Basket created",
      "basket.replaced": "Basket replaced",
      "basket.evaluated": "Basket evaluated",
      "evaluation.decided": "Approval decision",
      "order.attempted": "Order submitted",
      "order.refused": "Order refused",
      "order.created": "Order placed"
    }[event.type] || event.type || "Event";
    const codes = (event.reasonCodes || []).map(reasonLabel).join(", ");
    const summary = event.summary && event.summary.toLowerCase() !== label.toLowerCase() ? event.summary : "";
    return `<article class="event"><p class="mono">${esc(event.sequence ?? "")}</p><div><h3>${esc(label)}</h3>${summary ? `<p>${esc(summary)}</p>` : ""}${codes ? `<p class="hint">${esc(codes)}</p>` : ""}</div><p class="meta">${esc(roleLabel(event.actorId))}<br>${esc(formatStamp(event.at))}</p></article>`;
  }

  function reasonLabel(code) {
    return REASONS[code] || code || "Reason";
  }

  function reasonsBlock(reasons) {
    if (!Array.isArray(reasons) || !reasons.length) return "";
    return `<div class="stack-tight"><h2>Reported reasons</h2>${reasons.map((reason) => `<p><strong>${esc(reasonLabel(reason.code))}</strong> ${esc(reason.message || "")} ${reason.productId ? `<span class="mono">${esc(reason.productId)}</span>` : ""}</p>`).join("")}</div>`;
  }

  function decision(job, actions) {
    const evaluation = job.evaluation || {};
    const order = job.order;
    const total = (order || evaluation).totals;
    const limit = state.session && state.session.policy && state.session.policy.autonomousLimitMinor;
    const parts = [`<h2>Decision</h2>`];
    if (total) parts.push(`<p class="decision-total">${formatMinor(total.grossMinor)}</p>`);
    if (state.placing) {
      parts.push(progressList(state.placing, false));
      return parts.join("");
    }
    if (order) {
      parts.push(`<p><strong>Order placed</strong> · delivery ${esc(formatDay(order.requestedDeliveryDate || job.deliveryDate))}</p>`);
      parts.push(`<dl class="facts"><dt>Order number</dt><dd class="mono" title="${esc(order.id || "")}">${esc(orderNumber(order.id))}</dd><dt>Requested by</dt><dd>Chef (buyer)</dd><dt>Sourced by</dt><dd>Buyer agent</dd>${(evaluation.reasons || []).some((reason) => reason.code === "APPROVAL_THRESHOLD_EXCEEDED") ? `<dt>Approved by</dt><dd>Kitchen manager</dd>` : `<dt>Approval</dt><dd>Not needed (within limit)</dd>`}<dt>Placed by</dt><dd>${esc(roleLabel(order.committedBy))}</dd><dt>Placed</dt><dd>${esc(formatStamp(order.committedAt))}</dd></dl>`);
      parts.push(`<button type="button" class="button button-quiet" data-action="export">${icon("download")} Download order record</button>`);
      return parts.join("");
    }
    if (job.state === "needs_decision") parts.push(`<p>Answer the question to continue. Nothing is ordered yet.</p>`);
    else if (job.state === "awaiting_approval") parts.push(`<p>${actions.approve ? `Over the buyer's ${esc(formatMinor(limit))} limit. Your approval places the order.` : `Over your ${esc(formatMinor(limit))} limit, so it went to your kitchen manager.`}</p>`);
    else parts.push(`<p>${esc(decisionSummary(job))}</p>`);
    if (job.state === "blocked") parts.push(reasonsBlock(evaluation.reasons));
    if (state.confirm) parts.push(confirmBlock());
    else parts.push(`<div class="actions">${actionButtons(job, actions)}</div>`);
    return parts.join("");
  }

  function decisionSummary(job) {
    if (job.state === "ready") return job.evaluation && (job.evaluation.reasons || []).length ? "Approved. Ready to place." : "Within your limit. Ready to order.";
    if (job.state === "blocked") return "Can't be ordered as requested.";
    if (job.state === "needs_clarification") return "The agent needs more detail. Change the request.";
    if (job.state === "rejected") return "Rejected by the kitchen manager.";
    if (job.state === "failed") return job.error || "Something went wrong. Nothing was ordered.";
    if (job.state === "cancelled") return "Cancelled. Nothing was ordered.";
    return "Working…";
  }

  function actionButtons(job, actions) {
    const buttons = [];
    if (actions.approve) buttons.push(`<button type="button" class="button button-primary button-big" data-action="ask-approve">${icon("circle-check")} Approve &amp; place order</button>`);
    if (actions.reject) buttons.push(`<button type="button" class="button button-quiet" data-action="ask-reject">Reject</button>`);
    if (job.state === "ready" && hasScope(state.session, "orders:commit")) buttons.push(`<button type="button" class="button button-primary button-big" data-action="ask-commit">${icon("circle-check")} Place order</button>`);
    if (["blocked", "needs_clarification", "rejected", "failed"].includes(job.state) && actions.revise) buttons.push(`<button type="button" class="button button-secondary" data-action="revise">${icon("pencil")} Change the request</button>`);
    if (actions.cancel && !actions.approve) buttons.push(`<button type="button" class="button button-quiet" data-action="ask-cancel">Cancel request</button>`);
    return buttons.join("");
  }

  function confirmBlock() {
    const labels = { approve: "Approve and place this order? Price and stock are checked once more.", reject: "Reject this order?", commit: "Place this order? Price and stock are checked once more.", cancel: "Cancel this request?" };
    const tone = state.confirm === "reject" || state.confirm === "cancel" ? "button-danger" : "button-primary";
    return `<div class="notice"><p>${esc(labels[state.confirm] || "Confirm this action?")}</p><div class="actions"><button type="button" class="button ${tone}" data-action="confirm" ${state.busy ? "disabled" : ""}>${state.busy ? "Working…" : "Yes, continue"}</button><button type="button" class="button button-quiet" data-action="dismiss">Back</button></div></div>`;
  }

  async function boot() {
    state.route = parseRoute();
    render();
    try {
      const session = await request("GET", "/workspace/session");
      applySession(session);
      await loadJobs();
      state.phase = "workspace";
      await followRoute();
    } catch (error) {
      if (error.status === 401) {
        clearAuth();
        state.phase = "login";
        state.error = "";
      } else {
        state.phase = "login";
        state.error = `The workspace session could not be loaded. ${error.message}`;
      }
      render();
    }
  }

  function applySession(session) {
    rememberSession(session || {});
    if (!state.draft.deliveryDate && session && session.today) state.draft.deliveryDate = addDays(session.today, 2);
  }

  async function loadJobs() {
    const payload = await request("GET", "/workspace/jobs");
    state.jobs = Array.isArray(payload) ? payload : (payload && payload.jobs) || [];
  }

  async function followRoute() {
    window.clearTimeout(state.pollTimer);
    if (state.route.view === "job" && state.route.id) await loadJob(state.route.id, true);
    render();
    schedulePoll();
  }

  async function loadJob(id, includeEvents) {
    const seq = ++state.jobSeq;
    state.busy = state.job && state.job.id === id ? state.busy : "job";
    try {
      const job = await request("GET", `/workspace/jobs/${encodeURIComponent(id)}`);
      if (seq !== state.jobSeq) return;
      state.job = job;
      if (!state.rank) state.rank = job.preference || "balanced";
      if (includeEvents || state.route.tab === "activity") await loadEvents(id, seq);
    } catch (error) {
      if (seq !== state.jobSeq) return;
      if (error.status === 401) return unauthenticated();
      state.error = error.message;
    } finally {
      if (seq === state.jobSeq) state.busy = "";
    }
  }

  async function loadEvents(id, seq) {
    const payload = await request("GET", `/workspace/jobs/${encodeURIComponent(id)}/events`);
    if (seq !== state.jobSeq) return;
    state.events = Array.isArray(payload) ? payload : (payload && payload.events) || [];
  }

  function schedulePoll() {
    window.clearTimeout(state.pollTimer);
    if (state.phase !== "workspace" || document.hidden) return;
    const current = state.route.view === "job" ? state.job : null;
    const listActive = state.jobs.some((job) => shouldPoll(job.state));
    const jobActive = current ? shouldPoll(current.state) : false;
    if (!listActive && !jobActive && state.jobs.length) return;
    state.pollTimer = window.setTimeout(poll, current && (isWorking(current) || revealing(current)) ? 700 : 2500);
  }

  async function poll() {
    if (state.phase !== "workspace" || state.busy) {
      schedulePoll();
      return;
    }
    try {
      // Stay well under the gateway's per-user rate limit: while the agent works, poll only the open order.
      const current = state.route.view === "job" ? state.job : null;
      const working = Boolean(current && (isWorking(current) || revealing(current)));
      state.pollCount = (state.pollCount || 0) + 1;
      if (!current || !working && state.pollCount % 3 === 0) await loadJobs();
      if (state.route.view === "job" && state.route.id) await loadJob(state.route.id, !working && state.pollCount % 3 === 0);
      state.notice = "";
    } catch (error) {
      if (error.status === 401) return unauthenticated();
      state.notice = error.retryAfter ? `Refresh was rate limited. Retry after ${error.retryAfter} seconds. The last loaded state is still shown.` : "Could not refresh. The last loaded state is still shown.";
    }
    render({ ifChanged: true });
    schedulePoll();
  }

  function unauthenticated() {
    clearAuth();
    state.phase = "login";
    state.error = "Sign in again. The session is missing or expired.";
    render();
  }

  async function submitLogin(form) {
    const token = form.loginToken.value.trim();
    if (!token) return setError("Enter the login token.");
    if (token.length < 32 || token.length > 256) return setError("Login tokens issued by this gateway are 32 to 256 characters.");
    state.busy = "login";
    state.error = "";
    render();
    try {
      const login = await request("POST", "/auth/login", { loginToken: token });
      form.loginToken.value = "";
      rememberSession(login);
      const session = await request("GET", "/workspace/session");
      applySession({ ...login, ...session, csrfToken: session.csrfToken || login.csrfToken });
      await loadJobs();
      state.phase = "workspace";
      state.busy = "";
      if (!location.hash) location.hash = "#requests";
      state.route = parseRoute();
      await followRoute();
    } catch (error) {
      state.busy = "";
      state.error = error.status === 403 ? "The login token was rejected. Open this page from the gateway origin and check the token." : error.message;
      render();
    }
  }

  async function submitRequest() {
    syncDraft();
    const built = buildJobBody(state.draft, state.session);
    state.fieldErrors = built.errors;
    if (!built.ok) {
      state.error = "The request is incomplete.";
      render();
      return;
    }
    const pending = readPending();
    const key = pending && stable(pending.body) === stable(built.body) ? pending.key : uuid();
    storageSet(PENDING_KEY, JSON.stringify({ key, body: built.body }));
    state.busy = "submit";
    state.error = "";
    state.notice = "";
    render();
    try {
      const job = await request("POST", "/workspace/jobs", built.body, { "X-Request-Key": key });
      storageSet(PENDING_KEY, "");
      state.busy = "";
      state.draft = emptyDraft();
      if (state.session && state.session.today) state.draft.deliveryDate = addDays(state.session.today, 2);
      state.ask = "";
      state.understood = null;
      state.showForm = false;
      state.job = job;
      startReveal(job, false);
      go(`#job/${job.id}/basket`);
    } catch (error) {
      state.busy = "";
      if (error.status === 401) return unauthenticated();
      state.error = error.message;
      render();
    }
  }

  async function interpretAsk() {
    const text = (state.ask || "").trim();
    if (!text) return setError("Tell me what you need first.");
    state.busy = "interpret";
    state.error = "";
    state.understood = null;
    state.showForm = false;
    state.thinking = [{ label: "Reading your request", done: false }];
    render();
    try {
      const started = Date.now();
      const result = await request("POST", "/workspace/interpret", { text });
      await pace(450 - (Date.now() - started));
      const fields = result.fields || {};
      const found = result.kind === "recipe" ? [chipValue("style", fields.style || {}), fields.servings && fields.servings.value ? `${fields.servings.value} guests` : ""]
        : [chipValue("items", fields.items || { value: [] })];
      if (fields.deliveryDate && fields.deliveryDate.value) found.push(formatDay(fields.deliveryDate.value));
      state.thinking = [{ label: "Reading your request", detail: found.filter(Boolean).join(" · ") || "unclear" },
        { label: "Checking what's missing", done: false }];
      render();
      await pace(450);
      const questions = (result.questions || []).length;
      const assumed = Object.values(fields).filter((field) => field && field.source === "default").length;
      state.thinking[1] = { label: "Checking what's missing", detail: questions ? `${questions} question${questions > 1 ? "s" : ""} for you` : `nothing missing${assumed ? ` · ${assumed} assumed` : ""}` };
      render();
      await pace(300);
      state.understood = result;
      applyUnderstood(result);
    } catch (error) {
      if (error.status === 401) return unauthenticated();
      state.error = error.message;
    } finally {
      state.busy = "";
      state.thinking = null;
      render();
    }
  }

  function applyUnderstood(result) {
    const fields = result.fields || {};
    const value = (name, fallback) => fields[name] && fields[name].value != null ? fields[name].value : fallback;
    const draft = emptyDraft();
    draft.brief = result.brief || result.text || "";
    draft.style = value("style", "");
    draft.servings = String(value("servings", ""));
    draft.deliveryDate = value("deliveryDate", state.session && state.session.today ? addDays(state.session.today, 2) : "");
    draft.budget = value("budget", "") ? String(value("budget", "")).replace(/\.00$/, "") : "";
    draft.dietaryRequirements = value("dietaryRequirements", []);
    draft.excludedAllergens = value("excludedAllergens", []);
    draft.preference = value("preference", "balanced");
    draft.dietaryConfirmed = false;
    draft.autoCommit = true;
    draft.items = value("items", []);
    state.draft = draft;
  }

  function answerQuestion(field, value) {
    const result = state.understood;
    if (!result) return;
    if (field === "servings") {
      const input = document.getElementById("answer-servings");
      const number = Number(input && input.value);
      if (!Number.isInteger(number) || number < 1) return setError("Enter the number of guests.");
      value = number;
      state.draft.servings = String(number);
    }
    if (field === "style") state.draft.style = value;
    result.fields[field] = { value, source: "said", evidence: "your answer" };
    result.questions = (result.questions || []).filter((item) => item.field !== field);
    state.error = "";
    render();
  }

  function toggleMic() {
    if (state.listening && state.recognizer) {
      state.recognizer.stop();
      return;
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      state.notice = "Voice input needs Chrome or Edge. You can type the request instead.";
      return render();
    }
    const recognizer = new Recognition();
    recognizer.lang = navigator.language && navigator.language.startsWith("fi") ? "fi-FI" : "en-GB";
    recognizer.interimResults = true;
    recognizer.onresult = (event) => {
      state.ask = Array.from(event.results).map((item) => item[0].transcript).join("");
      const box = document.getElementById("ask");
      if (box) box.value = state.ask;
    };
    recognizer.onerror = () => { state.notice = "I couldn't hear that. Try again or type it."; };
    recognizer.onend = () => {
      state.listening = false;
      state.recognizer = null;
      render();
      if ((state.ask || "").trim()) interpretAsk();
    };
    state.listening = true;
    state.recognizer = recognizer;
    state.notice = "";
    render();
    recognizer.start();
  }

  function readPending() {
    try { return JSON.parse(storageGet(PENDING_KEY) || "null"); } catch (error) { return null; }
  }

  function stable(value) {
    return JSON.stringify(value);
  }

  async function mutate(path, body) {
    state.busy = "mutate";
    state.error = "";
    render();
    try {
      const job = await request("POST", path, body);
      state.job = job || state.job;
      state.confirm = "";
      state.comment = "";
      await loadJobs();
      if (state.job && state.job.id) await loadJob(state.job.id, true);
    } catch (error) {
      if (error.status === 401) return unauthenticated();
      state.error = error.status ? `${error.message} Reload before retrying if the server may already have recorded it.` : error.message;
    } finally {
      state.busy = "";
      render();
      schedulePoll();
    }
  }

  async function exportJob() {
    if (!state.job) return;
    try {
      const response = await fetch(`/workspace/jobs/${encodeURIComponent(state.job.id)}/export`, { credentials: "same-origin", cache: "no-store" });
      if (response.status === 401) return unauthenticated();
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(problemText(payload, response.status));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `aimo-job-${state.job.id}.json`;
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      state.error = error.message;
      render();
    }
  }

  function fillWedding() {
    syncDraft();
    state.draft.brief = "Pies for 100 wedding guests";
    state.draft.style = "savory";
    state.draft.servings = "100";
    state.notice = "Example filled. Choose a budget and confirm the dietary declaration before submitting.";
    render();
  }

  function fillMilk() {
    syncDraft();
    state.draft.brief = "12 litres lactose-free milk";
    state.draft.style = "not-a-pie";
    state.draft.servings = "1";
    state.draft.dietaryRequirements = ["lactose_free"];
    state.draft.excludedAllergens = state.draft.excludedAllergens.filter((item) => item !== "milk");
    state.draft.dietaryConfirmed = true;
    state.notice = "Lactose-free was confirmed by this example action. Milk was not excluded. Lactose-free is not milk-free.";
    render();
  }

  function useRecipe(id) {
    const recipe = (state.session.recipes || []).find((item) => item.id === id);
    if (!recipe) return;
    syncDraft();
    if (!state.draft.brief) state.draft.brief = recipe.title || recipe.id;
    else if (!state.draft.brief.includes(recipe.title || recipe.id)) state.draft.brief += `\nRecipe reference: ${recipe.title || recipe.id} (${recipe.id}).`;
    if (recipe.servings) state.draft.servings = String(recipe.servings);
    render();
  }

  function revise(job) {
    const parsed = parseStyle(job.brief || "");
    const next = emptyDraft();
    next.brief = parsed.brief;
    next.style = parsed.style;
    next.servings = job.servings == null ? "" : String(job.servings);
    next.deliveryDate = job.deliveryDate || next.deliveryDate;
    next.budget = minorToEuros(job.maxGrossMinor);
    next.preference = job.preference || "balanced";
    next.autoCommit = Boolean(job.autoCommit);
    next.scenario = job.scenario || "normal";
    next.dietaryRequirements = job.dietaryRequirements || (job.constraints && job.constraints.dietaryRequirements) || [];
    next.excludedAllergens = job.excludedAllergens || (job.constraints && job.constraints.excludedAllergens) || [];
    next.pantry = pantryRows(job);
    next.revisingFrom = job.id;
    next.dietaryConfirmed = false;
    next.items = job.items || [];
    state.draft = next;
    state.showForm = true;
    state.understood = null;
    state.notice = "Change what you need and submit again. Please confirm the diet again.";
    go("#requests");
  }

  function pantryRows(job) {
    if (job.pantry && typeof job.pantry === "object") return Object.entries(job.pantry).map(([key, amount]) => ({ key, amount: String(amount) }));
    const ingredients = job.plan && job.plan.ingredients || [];
    return ingredients.filter((item) => item.key).map((item) => ({ key: item.key, amount: item.pantry ?? "" }));
  }

  function setError(message) {
    state.error = message;
    render();
  }

  function onClick(event) {
    const button = event.target.closest("[data-action]");
    if (!button || button.disabled) return;
    syncDraft();
    const action = button.dataset.action;
    if (action === "reload") return reload();
    if (action === "logout") return logout();
    if (action === "mic") return toggleMic();
    if (action === "example") {
      state.ask = button.dataset.text;
      return interpretAsk();
    }
    if (action === "show-form") {
      state.showForm = true;
      return render();
    }
    if (action === "hide-form") {
      state.showForm = false;
      return render();
    }
    if (action === "answer") return answerQuestion(button.dataset.field, button.dataset.value);
    if (action === "find") return submitRequest();
    if (action === "resolve" && state.job) {
      startReveal(state.job, true);
      state.reveal.resolving = true;
      return mutate(`/workspace/jobs/${encodeURIComponent(state.job.id)}/resolve`, { exceptionId: button.dataset.exception, optionId: button.dataset.option });
    }
    if (action === "fill-wedding") return fillWedding();
    if (action === "fill-milk") return fillMilk();
    if (action === "use-recipe") return useRecipe(button.dataset.id);
    if (action === "add-pantry") {
      state.draft.pantry.push({ key: "", amount: "" });
      return render();
    }
    if (action === "remove-pantry") {
      state.draft.pantry.splice(Number(button.dataset.index), 1);
      return render();
    }
    if (action === "step") return step(button.dataset.target, Number(button.dataset.delta));
    if (action === "tab") return go(`#job/${state.route.id}/${button.dataset.tab}`);
    if (action === "revise" && state.job) return revise(state.job);
    if (action === "use-ranking") return useRanking();
    if (action === "export") return exportJob();
    if (action === "recheck" && state.job) return mutate(`/workspace/jobs/${encodeURIComponent(state.job.id)}/recheck`, {});
    if (action === "retry-pending") return retryPending();
    if (action === "discard-pending") {
      storageSet(PENDING_KEY, "");
      return render();
    }
    if (action.startsWith("ask-")) {
      state.confirm = action.slice(4);
      return render();
    }
    if (action === "dismiss") {
      state.confirm = "";
      return render();
    }
    if (action === "confirm") return confirmAction();
  }

  function step(target, delta) {
    const input = document.getElementById(target);
    if (!input) return;
    const current = Number(input.value || 0);
    const next = Math.min(10000, Math.max(1, (Number.isInteger(current) ? current : 0) + delta));
    input.value = String(next);
    state.draft[target] = input.value;
  }

  function useRanking() {
    if (!state.job) return;
    revise(state.job);
    state.draft.preference = state.rank || state.job.preference || "balanced";
    state.notice = "Ranking was copied into a new request. The previous approval will not apply.";
  }

  async function approveAndPlace() {
    const job = state.job;
    const id = encodeURIComponent(job.id);
    state.confirm = "";
    state.error = "";
    const steps = [];
    const run = async (label, detail, call) => {
      steps.push({ label, done: false });
      state.placing = steps;
      render();
      const started = Date.now();
      const result = await call();
      await pace(600 - (Date.now() - started));
      steps[steps.length - 1] = { label, detail };
      render();
      return result;
    };
    state.busy = "mutate";
    try {
      if (evaluationExpired(job, Date.now())) await run("Re-checked price & stock", "last check was over 2 min ago", () => request("POST", `/workspace/jobs/${id}/recheck`, {}));
      await run("Approved", roleLabel(state.session.principalId), () => request("POST", `/workspace/jobs/${id}/decision`, { decision: "approve" }));
      await run("Final price & stock check → order placed", "", () => request("POST", `/workspace/jobs/${id}/commit`, {}));
      await pace(500);
    } catch (error) {
      if (error.status === 401) return unauthenticated();
      state.error = error.message;
    } finally {
      state.placing = null;
      state.busy = "";
      await loadJobs();
      await loadJob(job.id, true);
      render();
      schedulePoll();
    }
  }

  async function confirmAction() {
    if (!state.job) return;
    const id = state.job.id;
    if (state.confirm === "approve") return approveAndPlace();
    if (state.confirm === "approve" || state.confirm === "reject") {
      const body = { decision: state.confirm === "approve" ? "approve" : "reject" };
      if (state.comment.trim()) body.comment = state.comment.trim();
      return mutate(`/workspace/jobs/${encodeURIComponent(id)}/decision`, body);
    }
    if (state.confirm === "commit") return mutate(`/workspace/jobs/${encodeURIComponent(id)}/commit`, {});
    if (state.confirm === "cancel") return mutate(`/workspace/jobs/${encodeURIComponent(id)}/cancel`, {});
  }

  async function retryPending() {
    const pending = readPending();
    if (!pending) return;
    state.busy = "submit";
    render();
    try {
      const job = await request("POST", "/workspace/jobs", pending.body, { "X-Request-Key": pending.key });
      storageSet(PENDING_KEY, "");
      state.busy = "";
      state.job = job;
      go(`#job/${job.id}/basket`);
    } catch (error) {
      state.busy = "";
      if (error.status === 401) return unauthenticated();
      state.error = error.message;
      render();
    }
  }

  async function reload() {
    state.error = "";
    state.notice = "";
    try {
      const session = await request("GET", "/workspace/session");
      applySession(session);
      await loadJobs();
      if (state.route.view === "job" && state.route.id) await loadJob(state.route.id, true);
    } catch (error) {
      if (error.status === 401) return unauthenticated();
      state.error = error.message;
    }
    render();
    schedulePoll();
  }

  async function logout() {
    try { await request("POST", "/workspace/logout", {}); } catch (error) { /* local sign-out still proceeds after a failed revoke */ }
    clearAuth();
    state.phase = "login";
    state.error = "";
    state.notice = "";
    render();
  }

  function mount() {
    document.addEventListener("click", onClick);
    document.addEventListener("submit", (event) => {
      if (event.target.id === "login-form") {
        event.preventDefault();
        submitLogin(event.target);
      }
      if (event.target.id === "request-form") {
        event.preventDefault();
        submitRequest();
      }
      if (event.target.id === "ask-form") {
        event.preventDefault();
        interpretAsk();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.target.id === "ask" && event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        interpretAsk();
      }
    });
    document.addEventListener("input", (event) => {
      if (event.target.id === "ask") state.ask = event.target.value;
      if (event.target.closest("#request-form, #request-filter, #decision-comment, #rank-preference")) syncDraft();
    });
    document.addEventListener("change", (event) => {
      if (event.target.dataset && event.target.dataset.bind) {
        state.draft[event.target.dataset.bind] = event.target.checked;
        render();
      }
      if (event.target.closest("#request-form, #rank-preference")) {
        syncDraft();
        if (event.target.matches("select, input[type='checkbox']")) render();
      }
    });
    document.addEventListener("error", (event) => {
      if (event.target && event.target.tagName === "IMG") {
        const replacement = document.createElement("div");
        replacement.className = "placeholder";
        replacement.textContent = "Image failed to load";
        event.target.replaceWith(replacement);
      }
    }, true);
    window.addEventListener("hashchange", () => {
      state.route = parseRoute();
      state.confirm = "";
      state.error = "";
      if (state.phase === "workspace") followRoute();
      else render();
    });
    document.addEventListener("visibilitychange", schedulePoll);
    document.addEventListener("toggle", (event) => { if (event.target.classList && event.target.classList.contains("more-options")) state.moreOpen = event.target.open; }, true);
    boot();
  }

  function selfCheck() {
    const assert = (condition, message) => { if (!condition) throw new Error(message); };
    assert(eurosToMinor("12,5") === 1250, "comma euros");
    assert(eurosToMinor("10.00") === 1000, "dot euros");
    assert(eurosToMinor("1.234") === null, "three decimals");
    assert(addDays("2026-11-30", 2) === "2026-12-02", "date rollover");
    assert(parseStyle("Requested style: savory.\n\nPies").style === "savory", "style parse");
    const ranked = rankCandidates([{ productId: "a", purchaseGrossMinor: null }, { productId: "b", purchaseGrossMinor: 100 }, { productId: "c", purchaseGrossMinor: 200 }], "price");
    assert(ranked.map((item) => item.productId).join("") === "bca", "null price last");
    assert(imageChoice(null, "vegetable-pie").illustrative === true, "illustrative fallback");
    assert(imageChoice("https://example.test/a.jpg", "vegetable-pie").illustrative === false, "supplied image wins");
    assert(imageChoice(null, "demo-flour") === null, "no unrelated product photo");
    const session = { scopes: ["requests:create", "requests:cancel"], mode: "fixture", today: "2026-11-14" };
    const manager = { scopes: ["approvals:decide", "orders:commit"] };
    assert(availableActions({ state: "awaiting_approval" }, session, 0).approve === false, "chef cannot approve");
    assert(availableActions({ state: "awaiting_approval" }, manager, 0).approve === true, "manager can approve");
    assert(availableActions({ state: "ready", evaluation: { expiresAt: "2020-01-01T00:00:00Z" } }, manager, Date.parse("2026-11-14T00:00:00Z")).commit === false, "expired commit hidden");
    assert(shouldPoll("ordered_mock") === false && shouldPoll("awaiting_approval") === true, "poll terminal states");
    const built = buildJobBody({ brief: "Milk", style: "not-a-pie", servings: "1", deliveryDate: "2026-11-16", budget: "22,20", preference: "balanced", dietaryConfirmed: true, dietaryRequirements: ["lactose_free"], excludedAllergens: [], pantry: [{ key: "milk", amount: "0" }], scenario: "shortage", autoCommit: false }, session);
    assert(built.ok && built.body.maxGrossMinor === 2220 && built.body.scenario === "shortage", "fixture body");
    const live = buildJobBody(built.body ? { brief: "Milk", style: "not-a-pie", servings: "1", deliveryDate: "2026-11-16", budget: "10", preference: "price", dietaryConfirmed: true, dietaryRequirements: [], excludedAllergens: [], pantry: [], autoCommit: true } : {}, { mode: "live", today: "2026-11-14" });
    assert(live.ok && !("scenario" in live.body) && live.body.autoCommit === true, "live omits scenario");
    assert(buildJobBody({ ...emptyDraft(), brief: "Pies" }, session).ok === false, "incomplete blocked");
    console.log("aimo workspace helpers ok");
  }

  return { mount, selfCheck, eurosToMinor, buildJobBody, availableActions, imageChoice, rankCandidates, shouldPoll };
});
