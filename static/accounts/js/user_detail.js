
const canEdit = {{ can_edit|yesno:"true,false" }};// prettier-ignore
const canResetPassword = {{ can_reset_password|yesno:"true,false" }};
const canDelete = {{ can_delete|yesno:"true,false" }};

const userId = {{ user_obj.pk }};
$(document).ready(function () {
  // Initialize login chart
  const loginChartOptions = {
    series: [{
      name: 'Successful Logins',
      data: [8, 12, 6, 15, 10, 18, 22] // Sample data - replace with actual data
    }, {
      name: 'Failed Logins',
      data: [2, 1, 3, 0, 2, 1, 0] // Sample data - replace with actual data
    }],
    chart: {
      type: 'area',
      height: 300,
      toolbar: {
        show: false
      }
    },
    colors: ['#667eea', '#dc3545'],
    dataLabels: {
      enabled: false
    },
    stroke: {
      curve: 'smooth',
      width: 2
    },
    xaxis: {
      categories: ['6 days ago', '5 days ago', '4 days ago', '3 days ago', '2 days ago', 'Yesterday', 'Today']
    },
    yaxis: {
      title: {
        text: 'Number of Logins'
      }
    },
    legend: {
      position: 'top'
    },
    grid: {
      borderColor: '#f1f3f4'
    }
  };

  // Only initialize chart if ApexCharts is available
  if (typeof ApexCharts !== 'undefined') {
    const loginChart = new ApexCharts(document.querySelector("#loginChart"), loginChartOptions);
    loginChart.render();
  } else {
    document.querySelector("#loginChart").innerHTML = '<div class="text-center py-4 text-muted">Chart library not loaded</div>';
  }

  // Initialize tooltips
  $('[data-bs-toggle="tooltip"]').tooltip();
});

// Utility functions
function showToast(message, type = 'info') {
  console.log(`${type.toUpperCase()}: ${message}`);
  alert(message); // Simple fallback
}

function showLoading() {
  console.log('Loading...');
}

function hideLoading() {
  console.log('Loading complete');
}

// Password Reset Function
function resetPassword() {
  const modal = new bootstrap.Modal(document.getElementById('passwordResetModal'));
  modal.show();
}

function confirmPasswordReset() {
  showLoading();

  $.post(`/accounts/users/${userId}/reset-password/`)
    .done(function (response) {
      hideLoading();
      if (response.success) {
        showToast(`Password reset successfully. Temporary password: ${response.temporary_password}`, 'success');
      } else {
        showToast(response.error, 'error');
      }
    })
    .fail(function () {
      hideLoading();
      showToast('An error occurred while resetting password', 'error');
    });

  bootstrap.Modal.getInstance(document.getElementById('passwordResetModal')).hide();
}

// Delete User Function
function confirmDelete() {
  const modal = new bootstrap.Modal(document.getElementById('deleteUserModal'));
  modal.show();
}

// Enable delete button when checkbox is checked
document.getElementById('confirmDelete').addEventListener('change', function () {
  document.getElementById('deleteButton').disabled = !this.checked;
});

function executeDelete() {
  showLoading();
  // Redirect to delete confirmation page
  window.location.href = `/accounts/users/${userId}/delete/`;
}

// Auto-refresh session data every 30 seconds
setInterval(function () {
  // You can implement AJAX refresh for session data here
  // This is useful for monitoring active sessions in real-time
}, 30000);

// Keyboard shortcuts
document.addEventListener('keydown', function (e) {
  // Ctrl/Cmd + E to edit
  if ((e.ctrlKey || e.metaKey) && e.key === 'e' && canEdit) {
    e.preventDefault();
    window.location.href = `/accounts/users/${userId}/edit/`;
  }

  // Ctrl/Cmd + R to reset password
  if ((e.ctrlKey || e.metaKey) && e.key === 'r' && canResetPassword) {
    e.preventDefault();
    resetPassword();
  }
});

// Print functionality
function printProfile() {
  window.print();
}

// Export user data
function exportUserData() {
  showLoading();

  // Create a comprehensive user data object
  const userData = {
    profile: {
      name: '{{ user_obj.get_display_name|escapejs }}',
      email: '{{ user_obj.email|escapejs }}',
      username: '{{ user_obj.username|escapejs }}',
      phone: '{{ user_obj.phone_number|default:""|escapejs }}',
      dateJoined: '{{ user_obj.date_joined|date:"c" }}',
      lastLogin: '{{ user_obj.last_login|date:"c"|default:"" }}'
    },
    security: {
      isActive: {{ user_obj.is_active| yesno: "true,false"
}},
emailVerified: { { user_obj.email_verified | yesno: "true,false" } },
phoneVerified: { { user_obj.phone_verified | yesno: "true,false" } },
twoFactorEnabled: { { user_obj.two_factor_enabled | yesno: "true,false" } }
    },
roles: [
  {% for assignment in role_assignments %}
{
  name: '{{ assignment.role.name|escapejs }}',
    assignedDate: '{{ assignment.assigned_date|date:"c" }}',
      assignedBy: '{{ assignment.assigned_by.get_display_name|default:"System"|escapejs }}'
} {% if not forloop.last %}, {% endif %}
{% endfor %}
    ]
  };

// Convert to JSON and download
const dataStr = JSON.stringify(userData, null, 2);
const dataBlob = new Blob([dataStr], { type: 'application/json' });
const url = URL.createObjectURL(dataBlob);

const link = document.createElement('a');
link.href = url;
link.download = 'user_{{ user_obj.username }}_data.json';
link.click();

URL.revokeObjectURL(url);
hideLoading();

showToast('User data exported successfully', 'success');
