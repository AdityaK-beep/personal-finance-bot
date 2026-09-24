/**
 * Personal Finance Advisor Bot - Frontend Script
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Initialize today's date for date inputs if empty
  const todayStr = new Date().toISOString().split('T')[0];
  const dateInputs = document.querySelectorAll('input[type="date"]');
  dateInputs.forEach(input => {
    if (!input.value) {
      input.value = todayStr;
    }
  });

  // 2. Attach confirmation dialog to all delete forms
  const deleteForms = document.querySelectorAll('.form-delete-confirm');
  deleteForms.forEach(form => {
    form.addEventListener('submit', function (event) {
      const confirmed = window.confirm('Are you sure you want to delete this transaction record? This action cannot be undone.');
      if (!confirmed) {
        event.preventDefault();
      }
    });
  });

  // 3. Auto-dismiss alerts after 6 seconds
  const autoAlerts = document.querySelectorAll('.alert-dismissible');
  autoAlerts.forEach(alert => {
    setTimeout(() => {
      try {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        if (bsAlert) bsAlert.close();
      } catch (e) {
        // Fallback if bootstrap alert JS is not active
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 400);
      }
    }, 6000);
  });
});

/**
 * Helper to initialize the category expense Chart.js doughnut chart
 * @param {string} canvasId - Target canvas element ID
 * @param {Array<string>} labels - Category names
 * @param {Array<number>} values - Category amounts
 */
function initExpenseChart(canvasId, labels, values) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const total = values.reduce((sum, val) => sum + val, 0);

  // If all values are 0, display an empty state indicator
  if (total === 0) {
    const parent = canvas.parentElement;
    parent.innerHTML = `
      <div class="text-center py-5">
        <div class="text-muted mb-2">
          <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"></path>
          </svg>
        </div>
        <p class="text-muted small mb-0">No expenses recorded for this month yet.</p>
      </div>
    `;
    return;
  }

  const categoryColors = [
    '#6366f1', // Rent (indigo)
    '#38bdf8', // Groceries (sky blue)
    '#f59e0b', // Transport (amber)
    '#ec4899', // Entertainment (pink)
    '#10b981', // Utilities (emerald)
    '#94a3b8'  // Other (slate)
  ];

  new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: categoryColors.slice(0, labels.length),
        borderColor: '#1e293b',
        borderWidth: 2,
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#cbd5e1',
            font: { family: 'Inter', size: 12 },
            padding: 16,
            usePointStyle: true
          }
        },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#f8fafc',
          bodyColor: '#e2e8f0',
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: function (context) {
              const val = context.raw || 0;
              const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
              return ` ${context.label}: ₹${val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${pct}%)`;
            }
          }
        }
      },
      cutout: '70%'
    }
  });
}
