/**
 * OtherProteins - Main JavaScript
 * JavaScript funtzionalitate nagusia
 */

// Document ready
document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss flash messages after 10 seconds (only for flash messages, not info alerts)
    // Only dismiss alerts that are flash messages (in the main container, not in cards)
    const flashAlerts = document.querySelectorAll('main .container .alert:not(.alert-permanent)');
    flashAlerts.forEach(function(alert) {
        setTimeout(function() {
            try {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } catch (e) {
                // If Bootstrap Alert is not available, just hide it
                alert.style.display = 'none';
            }
        }, 10000); // 10 seconds instead of 5
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#' && href.length > 1) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });

    // Form validation enhancement
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
});

// Utility function to update cart count
function updateCartCount(count) {
    const cartBadge = document.querySelector('.cart-badge');
    const cartIcon = document.querySelector('.cart-icon-container');
    
    if (cartBadge) {
        if (count > 0) {
            cartBadge.textContent = count;
            cartBadge.style.display = 'flex';
        } else {
            cartBadge.style.display = 'none';
        }
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { updateCartCount };
}

