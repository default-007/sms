/**
 * DataTables configuration for the School Management System
 */

/**
 * Default DataTables configuration
 * @param {Object} options - Custom options to override defaults
 * @returns {Object} DataTables configuration object
 */
function getDataTablesConfig(options = {}) {
	const defaults = {
		responsive: true,
		language: {
			search: "",
			searchPlaceholder: "Search...",
			lengthMenu: "Show _MENU_ entries",
			info: "Showing _START_ to _END_ of _TOTAL_ entries",
			infoEmpty: "Showing 0 to 0 of 0 entries",
			infoFiltered: "(filtered from _MAX_ total entries)",
			paginate: {
				first: '<i class="fas fa-angle-double-left"></i>',
				previous: '<i class="fas fa-angle-left"></i>',
				next: '<i class="fas fa-angle-right"></i>',
				last: '<i class="fas fa-angle-double-right"></i>',
			},
		},
		dom: '<"row"<"col-md-6"l><"col-md-6"f>><"table-responsive"t><"row"<"col-md-6"i><"col-md-6"p>>',
		pagingType: "full_numbers",
		lengthMenu: [
			[10, 25, 50, 100, -1],
			[10, 25, 50, 100, "All"],
		],
		pageLength: 25,
		columnDefs: [{ defaultContent: "-", targets: "_all" }],
		initComplete: function () {
			// Style the search box
			const searchInput = document.querySelector(".dataTables_filter input");
			if (searchInput) {
				searchInput.classList.add("form-control");
				searchInput.style.marginLeft = "0.5rem";
			}

			// Style the length
			// Style the length selector
			const lengthSelect = document.querySelector(".dataTables_length select");
			if (lengthSelect) {
				lengthSelect.classList.add("form-select");
				lengthSelect.style.width = "auto";
				lengthSelect.style.display = "inline-block";
			}
		},
	};

	// Merge custom options with defaults
	return { ...defaults, ...options };
}

/**
 * Initialize a DataTable with server-side processing
 * @param {string} tableId - Table element ID
 * @param {string} apiEndpoint - API endpoint for data
 * @param {Array} columns - Column definitions
 * @param {Object} options - Additional options
 * @returns {Object} DataTable instance
 */
function initServerSideDataTable(tableId, apiEndpoint, columns, options = {}) {
	const table = document.getElementById(tableId);
	if (!table) return null;

	const config = getDataTablesConfig({
		processing: true,
		serverSide: true,
		ajax: {
			url: apiEndpoint,
			type: "GET",
			data: function (params) {
				// Add custom filter params if provided in options
				if (options.filterParams) {
					return { ...params, ...options.filterParams() };
				}
				return params;
			},
			dataSrc: function (json) {
				return json.data;
			},
		},
		columns: columns,
		...options,
	});

	return new DataTable(table, config);
}

/**
 * Export DataTable data to CSV
 * @param {Object} table - DataTable instance
 * @param {string} filename - Export filename
 */
function exportTableToCSV(table, filename) {
	const data = table.data().toArray();
	const headers = table
		.columns()
		.header()
		.toArray()
		.map((header) => header.innerText);

	let csvContent = headers.join(",") + "\n";

	data.forEach((row) => {
		const values = Object.values(row).map((value) => {
			// Handle strings with commas, quotes, etc.
			if (typeof value === "string") {
				value = value.replace(/"/g, '""');
				if (
					value.includes(",") ||
					value.includes('"') ||
					value.includes("\n")
				) {
					value = `"${value}"`;
				}
			}
			return value;
		});

		csvContent += values.join(",") + "\n";
	});

	downloadData(csvContent, filename, "text/csv");
}

/**
 * Print DataTable data
 * @param {Object} table - DataTable instance
 * @param {string} title - Report title
 * @param {Object} options - Print options
 */
function printTable(table, title, options = {}) {
	const defaults = {
		messageTop: null,
		messageBottom: null,
		exportOptions: {
			columns: ":visible",
		},
		header: true,
		footer: true,
		autoPrint: true,
		title: title,
	};

	const printOptions = { ...defaults, ...options };
	table.buttons.exportInfo.title = title;

	$.fn.dataTable.ext.buttons.print.action(null, table, null, printOptions);
}
