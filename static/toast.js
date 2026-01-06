/**
 * Toast notification system for Django messages
 * Handles both server-side Django messages and client-side HTMX responses
 */

// Map Django message levels to alert variants
function getAlertVariant(djangoLevel) {
	const levelMap = {
		'success': 'success',
		'error': 'danger',
		'warning': 'warn',
		'info': 'info',
		'debug': 'info'
	};
	// Handle combined tags like 'error message' or 'success message'
	const baseLevel = djangoLevel.split(' ')[0];
	return levelMap[baseLevel] || 'info';
}

// Get icon for alert variant (using unicode symbols)
function getIcon(variant) {
	const iconMap = {
		'success': '✓',
		'danger': '⚠',
		'warning': '⚠',
		'info': 'ℹ'
	};
	return iconMap[variant] || 'ℹ';
}

// Show toast notification
function showToast(message, level) {
	const variant = getAlertVariant(level);
	const icon = getIcon(variant);
	const container = document.getElementById('toast-container');

	// Create alert element
	const alert = document.createElement('div');
	alert.className = 'card card--' + variant + ' alert alert--' + variant + ' card--hard-border-' + variant;
	alert.innerHTML =
		'<span class="alert__icon">' + icon + '</span>' +
		'<span class="alert__message">' + message + '</span>' +
		'<button class="alert__close" aria-label="Close">×</button>';

	// Add close functionality
	alert.querySelector('.alert__close').addEventListener('click', function() {
		alert.style.animation = 'fadeOut 0.2s ease-out forwards';
		setTimeout(function() { alert.remove(); }, 200);
	});

	// Append to container
	container.appendChild(alert);

	// Auto-dismiss after 5 seconds
	// setTimeout(function() {
	// 	if (alert.parentNode) {
	// 		alert.style.animation = 'fadeOut 0.2s ease-out forwards';
	// 		setTimeout(function() { alert.remove(); }, 200);
	// 	}
	// }, 5000);
}

// Show toast notifications from Django messages
function showDjangoMessages() {
	if (window.djangoMessages && window.djangoMessages.length > 0) {
		window.djangoMessages.forEach(function(msg) {
			showToast(msg.message, msg.level);
		});
	}
}

// Show messages on page load
if (document.readyState === 'loading') {
	document.addEventListener('DOMContentLoaded', showDjangoMessages);
} else {
	showDjangoMessages();
}

// Handle HTMX responses that might include messages
document.body.addEventListener('htmx:afterSwap', function(event) {
	const messageElements = event.detail.target.querySelectorAll('[data-message]');
	messageElements.forEach(function(el) {
		const level = el.getAttribute('data-message-level') || 'info';
		const message = el.textContent.trim();
		showToast(message, level);
		el.remove();
	});
});

