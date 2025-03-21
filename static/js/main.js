/**
 * Main JavaScript file for the School Management System
 */

// Global Variables
let toastContainer;

// Document Ready
document.addEventListener("DOMContentLoaded", function () {
	// Initialize components
	initToasts();
	initPopovers();
	initTooltips();

	// Cache DOM elements
	toastContainer = document.getElementById("alerts-container");
});

/**
 * Initialize Bootstrap Toasts
 */
function initToasts() {
	const toastElList = document.querySelectorAll(".toast");
	toastElList.forEach((toast) => {
		new bootstrap.Toast(toast, {
			autohide: true,
			delay: 5000,
		});
	});
}

/**
 * Initialize Bootstrap Popovers
 */
function initPopovers() {
	const popoverTriggerList = document.querySelectorAll(
		'[data-bs-toggle="popover"]'
	);
	popoverTriggerList.forEach((popoverTriggerEl) => {
		new bootstrap.Popover(popoverTriggerEl);
	});
}

/**
 * Initialize Bootstrap Tooltips
 */
function initTooltips() {
	const tooltipTriggerList = document.querySelectorAll(
		'[data-bs-toggle="tooltip"]'
	);
	tooltipTriggerList.forEach((tooltipTriggerEl) => {
		new bootstrap.Tooltip(tooltipTriggerEl);
	});
}

/**
 * Show alert notification
 * @param {string} type - Alert type (success, danger, warning, info)
 * @param {string} message - Alert message
 */
function showAlert(type, message) {
	// Create toast element
	const toast = document.createElement("div");
	toast.className = "toast show alert-toast";
	toast.setAttribute("role", "alert");
	toast.setAttribute("aria-live", "assertive");
	toast.setAttribute("aria-atomic", "true");

	// Toast header
	const header = document.createElement("div");
	header.className = `toast-header bg-${type}`;

	const title = document.createElement("strong");
	title.className = "me-auto text-white";
	title.textContent = type.charAt(0).toUpperCase() + type.slice(1);

	const closeButton = document.createElement("button");
	closeButton.className = "btn-close btn-close-white";
	closeButton.setAttribute("type", "button");
	closeButton.setAttribute("data-bs-dismiss", "toast");
	closeButton.setAttribute("aria-label", "Close");

	header.appendChild(title);
	header.appendChild(closeButton);

	// Toast body
	const body = document.createElement("div");
	body.className = "toast-body";
	body.textContent = message;

	// Append elements
	toast.appendChild(header);
	toast.appendChild(body);

	// Add to container
	toastContainer.appendChild(toast);

	// Initialize and show toast
	const bsToast = new bootstrap.Toast(toast, {
		autohide: true,
		delay: 5000,
	});

	bsToast.show();

	// Remove toast after it's hidden
	toast.addEventListener("hidden.bs.toast", function () {
		toast.remove();
	});
}

/**
 * Format date to readable string
 * @param {string} dateString - Date string
 * @param {string} format - Format type (default, short, long)
 * @returns {string} Formatted date string
 */
function formatDate(dateString, format = "default") {
	if (!dateString) return "";

	const date = new Date(dateString);

	if (format === "short") {
		return date.toLocaleDateString();
	} else if (format === "long") {
		return date.toLocaleDateString(undefined, {
			weekday: "long",
			year: "numeric",
			month: "long",
			day: "numeric",
		});
	} else {
		return date.toLocaleDateString(undefined, {
			year: "numeric",
			month: "short",
			day: "numeric",
		});
	}
}

/**
 * Format time since given date
 * @param {string} dateString - Date string
 * @returns {string} Time ago string
 */
function timeAgo(dateString) {
	if (!dateString) return "";

	const date = new Date(dateString);
	const now = new Date();
	const diffTime = Math.abs(now - date);
	const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

	if (diffDays < 1) {
		const diffHours = Math.floor(diffTime / (1000 * 60 * 60));
		if (diffHours < 1) {
			const diffMinutes = Math.floor(diffTime / (1000 * 60));
			return diffMinutes < 1 ? "Just now" : `${diffMinutes}m ago`;
		}
		return `${diffHours}h ago`;
	} else if (diffDays < 7) {
		return `${diffDays}d ago`;
	} else if (diffDays < 30) {
		const diffWeeks = Math.floor(diffDays / 7);
		return `${diffWeeks}w ago`;
	} else {
		return formatDate(dateString, "short");
	}
}
