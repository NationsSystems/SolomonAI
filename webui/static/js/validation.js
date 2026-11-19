// Lightweight helper namespace to avoid globals
window.SolomonForm = (() => {

  /* -----------------------------------------------------------------------
     Eye Icons (Open = hidden, Slash = visible)
     ----------------------------------------------------------------------- */
  const EYE_OPEN = `
    <svg xmlns="http://www.w3.org/2000/svg"
         fill="none" viewBox="0 0 24 24"
         stroke-width="1.5" stroke="currentColor"
         width="22" height="22">
      <path stroke-linecap="round" stroke-linejoin="round"
            d="M2.036 12.322a1 1 0 010-.644C3.423 
               7.886 7.355 4.75 12 4.75c4.645 0 
               8.577 3.136 9.964 6.928a1 1 
               0 010 .644C20.577 16.114 
               16.645 19.25 12 19.25c-4.645 
               0-8.577-3.136-9.964-6.928z" />
      <path stroke-linecap="round" stroke-linejoin="round"
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>`;

  const EYE_SLASH = `
    <svg xmlns="http://www.w3.org/2000/svg"
         fill="none" viewBox="0 0 24 24"
         stroke-width="1.5" stroke="currentColor"
         width="22" height="22">
      <path stroke-linecap="round" stroke-linejoin="round"
            d="M3.98 8.223A10.477 10.477 0 001.706 12c1.527 
               3.75 5.236 6.75 10.294 6.75 1.652 0 3.226-.33 
               4.678-.93M6.28 6.28A10.45 10.45 0 0111.999 
               5.25c5.058 0 8.767 3 10.294 6.75a10.49 
               10.49 0 01-4.03 4.811M6.28 
               6.28L3 3m3.28 3.28l12.96 12.96" />
    </svg>`;

  function _getWrapperInput(toggleEl) {
    const wrapper = toggleEl.closest(".password-wrapper");
    if (!wrapper) return null;
    const input = wrapper.querySelector("input");
    if (!input || !input.id) return null;
    return input;
  }

  function _syncToggleIcon(toggleEl, inputEl) {
    if (!toggleEl || !inputEl) return;
    toggleEl.innerHTML = (inputEl.type === "password") ? EYE_OPEN : EYE_SLASH;
  }

  // Public API (backwards-compatible): togglePassword("passwordInputId")
  function togglePassword(id) {
    const field = document.getElementById(id);
    if (!field) return;

    field.type = (field.type === "password") ? "text" : "password";

    // If this input lives in a wrapper with a toggle, sync that toggle too
    const wrapper = field.closest(".password-wrapper");
    if (wrapper) {
      const toggleEl = wrapper.querySelector(".toggle-password");
      if (toggleEl) _syncToggleIcon(toggleEl, field);
    }
  }

  /* -----------------------------------------------------------------------
     Robust binding: Event delegation (never misses)
     - Works even if DOMContentLoaded timing is weird
     - Works even if elements are injected later
     ----------------------------------------------------------------------- */
  document.addEventListener("click", (e) => {
    const toggleEl = e.target.closest?.(".toggle-password");
    if (!toggleEl) return;

    const inputEl = _getWrapperInput(toggleEl);
    if (!inputEl) return;

    // Prevent the page-level handler (if any) from double-toggling.
    // If you WANT both, remove these two lines.
    e.preventDefault();
    e.stopPropagation();

    togglePassword(inputEl.id);

    // Ensure icon reflects final state
    _syncToggleIcon(toggleEl, inputEl);
  }, true);

  // Initial icon sync (safe: does not depend on DOMContentLoaded)
  function _initialSync() {
    document.querySelectorAll(".toggle-password").forEach((toggleEl) => {
      const inputEl = _getWrapperInput(toggleEl);
      if (!inputEl) return;
      _syncToggleIcon(toggleEl, inputEl);
    });
  }

  // Run now + after DOM ready (covers all timing cases)
  try { _initialSync(); } catch {}
  document.addEventListener("DOMContentLoaded", () => {
    try { _initialSync(); } catch {}
  });

  /* -----------------------------------------------------------------------
     Toasts (Phase 57 compatible)
     - Prefer portal-level showToast if present
     - Fallback to legacy global toast container if not
     ----------------------------------------------------------------------- */
  function showToast(message, type = "info") {
    if (typeof window.showToast === "function") {
      window.showToast(message, type);
      return;
    }

    let container = document.getElementById("toastContainer");
    if (!container) {
      container = document.createElement("div");
      container.id = "toastContainer";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    requestAnimationFrame(() => (toast.style.opacity = "1"));
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // Internal: set or clear one field’s error
  function setFieldError(fieldId, message = "", show = false) {
    const input = document.getElementById(fieldId);
    const err = document.getElementById(`error-${fieldId}`);
    if (!input || !err) return;

    if (show && message) {
      input.classList.add("input-error");
      err.textContent = message;
      err.style.display = "block";
    } else {
      input.classList.remove("input-error");
      err.textContent = "";
      err.style.display = "none";
    }
  }

  // Validate required fields. Expects <div id="error-<fieldId">...</div>
  // Returns { valid: boolean, errors: { fieldId: message } }
  function validateRequiredFields(formId, fields, { showErrors = false, messages = {} } = {}) {
    const result = { valid: true, errors: {} };
    fields.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;

      const value = (el.value || "").trim();
      if (!value) {
        result.valid = false;
        result.errors[id] = messages[id] || "Required";
        if (showErrors) setFieldError(id, result.errors[id], true);
      } else if (showErrors) {
        setFieldError(id, "", false);
      }
    });
    return result;
  }

  // Explicit username validation (prevent silent email-as-username failure)
  function validateUsernameNotEmail(usernameFieldId, { showErrors = false } = {}) {
    const el = document.getElementById(usernameFieldId);
    if (!el) return { valid: true };

    const value = (el.value || "").trim();
    if (value.includes("@")) {
      const message =
        "Usernames can’t be email addresses. Please enter a short name instead. No account was created.";
      if (showErrors) {
        setFieldError(usernameFieldId, message, true);
        showToast(message, "warning");
      }
      return { valid: false, error: message };
    }

    if (showErrors) setFieldError(usernameFieldId, "", false);
    return { valid: true };
  }

  // Small helper to remove error styles live while typing (optional)
  function attachLiveErrorClearing(fields) {
    fields.forEach((id) => {
      const el = document.getElementById(id);
      const err = document.getElementById(`error-${id}`);
      if (!el || !err) return;
      el.addEventListener("input", () => {
        if ((el.value || "").trim()) {
          setFieldError(id, "", false);
        }
      });
    });
  }

  return {
    togglePassword,
    showToast,
    validateRequiredFields,
    validateUsernameNotEmail,
    setFieldError,
    attachLiveErrorClearing,
  };
})();
