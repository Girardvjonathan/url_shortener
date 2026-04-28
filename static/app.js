(() => {
  // ── DOM refs ────────────────────────────────────────────────────
  const form       = document.getElementById('shorten-form');
  const input      = document.getElementById('url-input');
  const submitBtn  = document.getElementById('submit-btn');
  const btnLabel   = submitBtn.querySelector('.btn-label');
  const btnSpinner = submitBtn.querySelector('.btn-spinner');

  const resultCard    = document.getElementById('result-card');
  const resultBadge   = document.getElementById('result-badge');
  const resultLink    = document.getElementById('result-link');
  const resultOriginal= document.getElementById('result-original');
  const copyBtn       = document.getElementById('copy-btn');
  const iconCopy      = copyBtn.querySelector('.icon-copy');
  const iconCheck     = copyBtn.querySelector('.icon-check');

  const urlsTable  = document.getElementById('urls-table');
  const urlsTbody  = document.getElementById('urls-tbody');
  const urlsEmpty  = document.getElementById('urls-empty');
  const urlCount   = document.getElementById('url-count');

  const toast      = document.getElementById('toast');

  // ── Toast ───────────────────────────────────────────────────────
  let toastTimer;
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2400);
  }

  // ── Copy helper ─────────────────────────────────────────────────
  function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      btn.classList.add('copied');
      const copy  = btn.querySelector('.icon-copy');
      const check = btn.querySelector('.icon-check');
      if (copy)  copy.hidden  = true;
      if (check) check.hidden = false;
      showToast('Copied to clipboard!');
      setTimeout(() => {
        btn.classList.remove('copied');
        if (copy)  copy.hidden  = false;
        if (check) check.hidden = true;
      }, 2000);
    });
  }

  // ── Result card copy button ──────────────────────────────────────
  copyBtn.addEventListener('click', () => {
    copyText(resultLink.href, copyBtn);
  });

  // ── Suggestion chips ─────────────────────────────────────────────
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      input.value = chip.dataset.url;
      input.focus();
    });
  });

  // ── Inline input error ───────────────────────────────────────────
  const errorEl = document.getElementById('input-error');

  function showInputError(msg) {
    errorEl.textContent = msg;
    errorEl.hidden = false;
    input.classList.add('input-error');
  }

  function clearInputError() {
    errorEl.hidden = true;
    errorEl.textContent = '';
    input.classList.remove('input-error');
  }

  input.addEventListener('input', clearInputError);

  function extractApiError(err) {
    if (Array.isArray(err.detail)) {
      return err.detail.map(e => e.msg).join(', ');
    }
    return err.detail || 'Something went wrong.';
  }

  // ── Shorten form ─────────────────────────────────────────────────
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearInputError();
    const url = input.value.trim();
    if (!url) return;

    // Auto-prefix if missing protocol
    const normalized = /^https?:\/\//i.test(url) ? url : `https://${url}`;

    // Loading state
    btnLabel.hidden  = true;
    btnSpinner.hidden = false;
    submitBtn.disabled = true;

    try {
      const res = await fetch('/api/shorten', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_url: normalized }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const msg = extractApiError(err);
        showInputError(msg);
        showToast(msg);
        return;
      }

      const data = await res.json();
      showResultCard(data);
      await loadRecentUrls();
    } catch {
      const msg = 'Network error — please try again.';
      showInputError(msg);
      showToast(msg);
    } finally {
      btnLabel.hidden   = false;
      btnSpinner.hidden = true;
      submitBtn.disabled = false;
    }
  });

  // ── Render result card ───────────────────────────────────────────
  function showResultCard(data) {
    resultLink.href        = data.short_url;
    resultLink.textContent = data.short_url;
    resultOriginal.textContent = data.full_url;
    resultBadge.textContent    = data.is_new ? 'New' : 'Existing';

    // Re-trigger animation
    resultCard.hidden = false;
    resultCard.style.animation = 'none';
    requestAnimationFrame(() => {
      resultCard.style.animation = '';
    });

    // Reset copy button
    copyBtn.classList.remove('copied');
    iconCopy.hidden  = false;
    iconCheck.hidden = true;
  }

  // ── Render recent URLs table ─────────────────────────────────────
  async function loadRecentUrls() {
    try {
      const res = await fetch('/api/urls');
      if (!res.ok) return;
      const urls = await res.json();

      if (urls.length === 0) {
        urlsTable.hidden = true;
        urlsEmpty.hidden = false;
        urlCount.textContent = '';
        return;
      }

      urlsEmpty.hidden = true;
      urlsTable.hidden = false;
      urlCount.textContent = `${urls.length} link${urls.length !== 1 ? 's' : ''}`;

      urlsTbody.innerHTML = '';
      urls.forEach((item, i) => {
        const tr = document.createElement('tr');
        tr.style.animationDelay = `${i * 35}ms`;
        tr.innerHTML = `
          <td><a class="table-short-link" href="${esc(item.short_url)}" target="_blank" rel="noopener">${esc(item.short_url)}</a></td>
          <td><span class="table-full-url" title="${esc(item.full_url)}">${esc(item.full_url)}</span></td>
          <td class="table-clicks col-clicks">${item.click_count}</td>
          <td class="col-copy">
            <button class="table-copy-btn" title="Copy short link" data-url="${esc(item.short_url)}">
              <svg class="icon-copy" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
              <svg class="icon-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" hidden>
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </button>
          </td>
        `;
        urlsTbody.appendChild(tr);
      });

      // Copy buttons in table
      urlsTbody.querySelectorAll('.table-copy-btn').forEach(btn => {
        btn.addEventListener('click', () => copyText(btn.dataset.url, btn));
      });

    } catch {
      // Silently ignore — table just stays empty
    }
  }

  // ── HTML escaping ────────────────────────────────────────────────
  function esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Init ─────────────────────────────────────────────────────────
  loadRecentUrls();
})();
