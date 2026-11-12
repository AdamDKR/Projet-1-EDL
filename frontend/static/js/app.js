/**
 * Partage de frais - Client Application Script
 * Modal management, participant toggles, and client-side form validation.
 */

document.addEventListener("DOMContentLoaded", () => {
  initModals();
  initGroupValidation();
  initParticipantToggles();
  initExpenseValidation();
  initReimbursementValidation();
  initAlertDismissals();
  initGroupSelector();
});

/**
 * Modal dialog handling (open, close, escape key, backdrop click).
 */
function initModals() {
  const openButtons = document.querySelectorAll("[data-modal-target], #open-new-group-modal");
  const closeButtons = document.querySelectorAll("[data-modal-close], .modal-close-btn");

  function openModal(modal) {
    if (!modal) return;
    modal.classList.add("is-active");
    modal.setAttribute("aria-hidden", "false");
    const firstInput = modal.querySelector("input:not([type=hidden]), select, textarea") || modal.querySelector("button");
    if (firstInput) {
      setTimeout(() => firstInput.focus(), 50);
    }
  }

  function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove("is-active");
    modal.setAttribute("aria-hidden", "true");
  }

  openButtons.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = btn.getAttribute("data-modal-target") || "modal-new-group";
      const modal = document.getElementById(targetId);
      openModal(modal);
    });
  });

  closeButtons.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const modal = btn.closest(".modal-backdrop");
      closeModal(modal);
    });
  });

  // Close when clicking directly on backdrop
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) {
        closeModal(backdrop);
      }
    });
  });

  // Close on Escape key press
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-backdrop.is-active").forEach((modal) => {
        closeModal(modal);
      });
    }
  });
}

/**
 * Validate new group modal form (start_date <= end_date).
 */
function initGroupValidation() {
  const modalForm = document.querySelector("#modal-new-group form");
  if (!modalForm) return;

  modalForm.addEventListener("submit", (e) => {
    const startInput = modalForm.querySelector('input[name="start_date"]');
    const endInput = modalForm.querySelector('input[name="end_date"]');
    if (startInput && endInput && startInput.value && endInput.value) {
      if (startInput.value > endInput.value) {
        e.preventDefault();
        alert("La date de début du séjour ne peut pas être postérieure à la date de fin.");
        endInput.focus();
        return false;
      }
    }
    return true;
  });
}

/**
 * Toggle all participants checkbox helper.
 */
function initParticipantToggles() {
  const toggleBtn = document.getElementById("toggle-all-participants");
  const checkboxes = document.querySelectorAll('input[name="participants"]');
  const errorEl = document.getElementById("participants-error");
  const container = document.getElementById("participants-list");

  if (!toggleBtn || checkboxes.length === 0) return;

  function updateButtonLabel() {
    const allChecked = Array.from(checkboxes).every((cb) => cb.checked);
    toggleBtn.textContent = allChecked ? "Tout désélectionner" : "Tout sélectionner";
  }

  toggleBtn.addEventListener("click", (e) => {
    e.preventDefault();
    const allChecked = Array.from(checkboxes).every((cb) => cb.checked);
    checkboxes.forEach((cb) => {
      cb.checked = !allChecked;
    });
    updateButtonLabel();

    // Clear validation error if user selected all
    if (!allChecked) {
      if (errorEl) errorEl.style.display = "none";
      if (container) container.style.borderColor = "";
    }
  });

  checkboxes.forEach((cb) => {
    cb.addEventListener("change", () => {
      updateButtonLabel();
      const anyChecked = Array.from(checkboxes).some((c) => c.checked);
      if (anyChecked) {
        if (errorEl) errorEl.style.display = "none";
        if (container) container.style.borderColor = "";
      }
    });
  });

  updateButtonLabel();
}


/**
 * Client-side validation ensuring >= 1 participant selected and dates bounded.
 */
function initExpenseValidation() {
  const form = document.getElementById("expense-form");
  if (!form) return;

  form.addEventListener("submit", (e) => {
    const checkboxes = form.querySelectorAll('input[name="participants"]:checked');
    const errorEl = document.getElementById("participants-error");
    const container = document.getElementById("participants-list");

    if (checkboxes.length === 0) {
      e.preventDefault();
      if (errorEl) {
        errorEl.textContent = "Veuillez sélectionner au moins un participant pour cette dépense.";
        errorEl.style.display = "block";
      }
      if (container) {
        container.style.borderColor = "var(--danger)";
        container.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      return false;
    }

    if (container) {
      container.style.borderColor = "var(--border)";
    }
    if (errorEl) {
      errorEl.style.display = "none";
    }

    // Verify date is within bounds
    const dateInput = form.querySelector('input[name="date"]');
    if (dateInput && dateInput.value) {
      const minDate = dateInput.getAttribute("min");
      const maxDate = dateInput.getAttribute("max");
      if (minDate && dateInput.value < minDate) {
        e.preventDefault();
        alert(`La date de la dépense (${dateInput.value}) ne peut pas être antérieure au début du séjour (${minDate}).`);
        dateInput.focus();
        return false;
      }
      if (maxDate && dateInput.value > maxDate) {
        e.preventDefault();
        alert(`La date de la dépense (${dateInput.value}) ne peut pas être postérieure à la fin du séjour (${maxDate}).`);
        dateInput.focus();
        return false;
      }
    }

    // Verify amount is positive
    const amountInput = form.querySelector('input[name="amount"]');
    if (amountInput) {
      const val = parseFloat(amountInput.value.replace(",", "."));
      if (isNaN(val) || val <= 0) {
        e.preventDefault();
        alert("Le montant de la dépense doit être un nombre strictement positif.");
        amountInput.focus();
        return false;
      }
    }

    return true;
  });
}

/**
 * Client-side validation for reimbursement form (distinct members & positive amount).
 */
function initReimbursementValidation() {
  const form = document.getElementById("reimbursement-form");
  if (!form) return;

  form.addEventListener("submit", (e) => {
    const fromSelect = form.querySelector('select[name="from_member_id"]');
    const toSelect = form.querySelector('select[name="to_member_id"]');
    if (fromSelect && toSelect && fromSelect.value === toSelect.value) {
      e.preventDefault();
      alert("Un membre ne peut pas se rembourser lui-même. Veuillez choisir deux membres différents.");
      toSelect.focus();
      return false;
    }

    const amountInput = form.querySelector('input[name="amount"]');
    if (amountInput) {
      const val = parseFloat(amountInput.value.replace(",", "."));
      if (isNaN(val) || val <= 0) {
        e.preventDefault();
        alert("Le montant du remboursement doit être un nombre strictement positif.");
        amountInput.focus();
        return false;
      }
    }
    return true;
  });
}

/**
 * Dismiss flash alerts.
 */
function initAlertDismissals() {
  document.querySelectorAll(".alert-close").forEach((btn) => {
    btn.addEventListener("click", () => {
      const alert = btn.closest(".alert");
      if (alert) {
        alert.style.transition = "opacity 0.2s ease, transform 0.2s ease";
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-4px)";
        setTimeout(() => alert.remove(), 200);
      }
    });
  });
}

/**
 * Handle group selector change to redirect to selected group.
 */
function initGroupSelector() {
  const select = document.getElementById("group-select");
  if (!select) return;

  select.addEventListener("change", (e) => {
    const groupId = e.target.value;
    if (groupId) {
      window.location.href = `/?group_id=${encodeURIComponent(groupId)}`;
    }
  });
}
