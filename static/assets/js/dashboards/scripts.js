$(document).ready(function () {
  // Initialize DataTables
  {% if recent_activity %}
  $('#recentActivityTable').DataTable({
    "pageLength": 5,
    "lengthChange": false,
    "searching": false,
    "ordering": false,
    "info": false
  });
  {% endif %}

  // Financial Chart (for admin dashboard)
  {% if financial_summary and user_role == "system_admin" or user_role == "school_admin" or user_role == "superuser" %}
  var financialOptions = {
    series: [{
      name: 'Expected',
      data: [{{ financial_summary.total_expected|default: 0 }}]
  }, {
    name: 'Collected',
    data: [{{ financial_summary.total_collected|default: 0
}}]
    }],
  chart: {
  type: 'bar',
  height: 300
},
  plotOptions: {
  bar: {
    horizontal: false,
    columnWidth: '55%',
    endingShape: 'rounded'
  },
},
  dataLabels: {
  enabled: false
},
  stroke: {
  show: true,
  width: 2,
  colors: ['transparent']
},
  xaxis: {
  categories: ['Revenue'],
},
  yaxis: {
  title: {
    text: 'Amount'
  }
},
  fill: {
  opacity: 1
},
  tooltip: {
  y: {
    formatter: function (val) {
      return "$ " + val.toLocaleString()
    }
  }
}
  };

var financialChart = new ApexCharts(document.querySelector("#financialChart"), financialOptions);
financialChart.render();
{% endif %}
});