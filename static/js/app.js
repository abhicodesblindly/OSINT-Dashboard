// ========================================
// OSINT Dashboard — Frontend Application
// ========================================

(function () {
  "use strict";

  // --- State ---
  let currentMode = "email";
  let lastResult = null;
  let isScanning = false;

  // --- DOM References ---
  const btnEmail = document.getElementById("btn-email");
  const btnPhone = document.getElementById("btn-phone");
  const scanInput = document.getElementById("scan-input");
  const scanBtn = document.getElementById("scan-btn");
  const scanBtnText = document.getElementById("scan-btn-text");
  const scanSpinner = document.getElementById("scan-spinner");
  const resultsSection = document.getElementById("results-section");
  const exportBtn = document.getElementById("export-btn");
  const errorToast = document.getElementById("error-toast");
  const errorText = document.getElementById("error-text");
  const metadataBody = document.getElementById("metadata-body");
  const breachesBody = document.getElementById("breaches-body");
  const breachCount = document.getElementById("breach-count");
  const accountsBody = document.getElementById("accounts-body");
  const accountCount = document.getElementById("account-count");
  const inputLabel = document.getElementById("input-label");
  const scanTimestamp = document.getElementById("scan-timestamp");

  // --- Mode Toggle ---
  btnEmail.addEventListener("click", () => switchMode("email"));
  btnPhone.addEventListener("click", () => switchMode("phone"));

  function switchMode(mode) {
    currentMode = mode;
    if (mode === "email") {
      btnEmail.classList.add("active");
      btnPhone.classList.remove("active");
      scanInput.placeholder = "Enter email address…";
      scanInput.type = "email";
      inputLabel.textContent = "Email Address";
    } else {
      btnPhone.classList.add("active");
      btnEmail.classList.remove("active");
      scanInput.placeholder = "Enter phone number (e.g. +14155552671)…";
      scanInput.type = "tel";
      inputLabel.textContent = "Phone Number";
    }
    scanInput.value = "";
    scanInput.focus();
  }

  // --- Scan ---
  scanBtn.addEventListener("click", performScan);
  scanInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") performScan();
  });

  async function performScan() {
    const value = scanInput.value.trim();
    if (!value) {
      showError("Please enter a value to scan.");
      return;
    }

    if (isScanning) return;
    isScanning = true;
    setLoading(true);
    hideError();
    hideResults();

    const endpoint =
      currentMode === "email" ? "/api/scan-email" : "/api/scan-phone";
    const body =
      currentMode === "email" ? { email: value } : { phone: value };

    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await resp.json();

      if (!data.success) {
        showError(data.error || "Scan failed. Please try again.");
        return;
      }

      lastResult = data;
      renderResults(data);
    } catch (err) {
      showError("Network error. Is the server running?");
    } finally {
      isScanning = false;
      setLoading(false);
    }
  }

  // --- Render Results ---
  function renderResults(data) {
    const d = data.data;

    // Timestamp
    if (scanTimestamp) {
      const ts = d.scan_timestamp || data.timestamp;
      scanTimestamp.textContent = `Scanned at ${new Date(ts).toLocaleString()}`;
      scanTimestamp.classList.remove("hidden");
    }

    // Metadata
    renderMetadata(d.metadata);

    // Breaches
    renderBreaches(d.breaches || []);

    // Accounts
    renderAccounts(d.accounts || []);

    // Show results with staggered animation
    resultsSection.classList.remove("hidden");
    const cards = resultsSection.querySelectorAll(".result-card");
    cards.forEach((card, i) => {
      card.style.opacity = "0";
      card.style.transform = "translateY(20px)";
      setTimeout(() => {
        card.style.transition = "all 0.5s cubic-bezier(0.4, 0, 0.2, 1)";
        card.style.opacity = "1";
        card.style.transform = "translateY(0)";
      }, i * 150);
    });

    exportBtn.classList.remove("hidden");
    exportBtn.style.opacity = "0";
    setTimeout(() => {
      exportBtn.style.transition = "opacity 0.4s ease";
      exportBtn.style.opacity = "1";
    }, 500);
  }

  function renderMetadata(meta) {
    if (!meta) {
      metadataBody.innerHTML =
        '<p class="text-slate-400">No metadata available.</p>';
      return;
    }

    let html = "";
    if (currentMode === "phone") {
      html = `
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">E.164 Format</span>
            <span class="meta-value">${esc(meta.e164 || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">International</span>
            <span class="meta-value">${esc(meta.international || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">National</span>
            <span class="meta-value">${esc(meta.national || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Country</span>
            <span class="meta-value">${esc(meta.country || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Region</span>
            <span class="meta-value">${esc(meta.region_code || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Country Code</span>
            <span class="meta-value">${esc(meta.country_code || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Carrier</span>
            <span class="meta-value">${esc(meta.carrier || "Unknown")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Line Type</span>
            <span class="meta-value line-type-badge">${esc(meta.line_type || "Unknown")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Timezone(s)</span>
            <span class="meta-value">${esc(
              Array.isArray(meta.timezones)
                ? meta.timezones.join(", ")
                : meta.timezones || "N/A"
            )}</span>
          </div>
        </div>`;
    } else {
      html = `
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">Email</span>
            <span class="meta-value">${esc(meta.email || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Username</span>
            <span class="meta-value">${esc(meta.username || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Domain</span>
            <span class="meta-value">${esc(meta.domain || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Provider</span>
            <span class="meta-value">${esc(meta.provider || "N/A")}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Format Valid</span>
            <span class="meta-value badge-ok">✓ Valid</span>
          </div>
        </div>`;
    }
    metadataBody.innerHTML = html;
  }

  function renderBreaches(breaches) {
    breachCount.textContent = breaches.length;

    if (breaches.length === 0) {
      breachesBody.innerHTML = `
        <div class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" class="empty-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <p>No breaches found — looking clean! 🛡️</p>
        </div>`;
      return;
    }

    let html = '<div class="breach-list">';
    breaches.forEach((b) => {
      html += `
        <div class="breach-item">
          <div class="breach-header">
            <span class="breach-name">${esc(b.name)}</span>
            <span class="breach-source">${esc(b.source)}</span>
          </div>
          <div class="breach-details">
            <span>📅 ${esc(String(b.date))}</span>
            <span>🌐 ${esc(String(b.domain))}</span>
            <span>📊 ${esc(String(b.records))} records</span>
          </div>
          <div class="breach-data-types">${esc(String(b.data_types))}</div>
        </div>`;
    });
    html += "</div>";
    breachesBody.innerHTML = html;
  }

  function renderAccounts(accounts) {
    const registered = accounts.filter((a) => a.registered);
    accountCount.textContent = registered.length;

    if (accounts.length === 0) {
      accountsBody.innerHTML = `
        <div class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" class="empty-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <p>No account data available. Install <code>holehe</code> / <code>ignorant</code> for platform detection.</p>
        </div>`;
      return;
    }

    let html = '<div class="accounts-grid">';

    // Show registered accounts first
    const sorted = [...accounts].sort((a, b) => (b.registered ? 1 : 0) - (a.registered ? 1 : 0));

    sorted.forEach((a) => {
      const statusClass = a.registered ? "acc-found" : "acc-not-found";
      const icon = a.registered ? "✅" : "❌";
      html += `
        <div class="account-chip ${statusClass}">
          <span class="acc-icon">${icon}</span>
          <span class="acc-name">${esc(a.platform)}</span>
        </div>`;
    });
    html += "</div>";
    accountsBody.innerHTML = html;
  }

  // --- Export ---
  exportBtn.addEventListener("click", () => {
    if (!lastResult) return;
    const blob = new Blob([JSON.stringify(lastResult, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const input = lastResult.data?.input || "scan";
    a.download = `osint_report_${input.replace(/[^a-zA-Z0-9]/g, "_")}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  // --- Helpers ---
  function setLoading(loading) {
    if (loading) {
      scanBtn.disabled = true;
      scanBtnText.textContent = "Scanning…";
      scanSpinner.classList.remove("hidden");
      scanBtn.classList.add("scanning");
    } else {
      scanBtn.disabled = false;
      scanBtnText.textContent = "Scan";
      scanSpinner.classList.add("hidden");
      scanBtn.classList.remove("scanning");
    }
  }

  function showError(msg) {
    errorText.textContent = msg;
    errorToast.classList.remove("hidden");
    errorToast.style.animation = "slideIn 0.4s ease-out";
    setTimeout(() => hideError(), 6000);
  }

  function hideError() {
    errorToast.classList.add("hidden");
  }

  function hideResults() {
    resultsSection.classList.add("hidden");
    exportBtn.classList.add("hidden");
    if (scanTimestamp) scanTimestamp.classList.add("hidden");
  }

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }
})();
