/**
 * Chart configuration for the School Management System
 */

/**
 * Default Chart.js configuration
 * @param {Object} options - Custom options to override defaults
 * @returns {Object} Chart.js configuration object
 */
function getDefaultChartConfig(options = {}) {
	const defaults = {
		responsive: true,
		maintainAspectRatio: false,
		plugins: {
			legend: {
				position: "top",
				labels: {
					font: {
						family: "'Nunito', sans-serif",
						size: 12,
					},
					usePointStyle: true,
					padding: 20,
				},
			},
			tooltip: {
				backgroundColor: "rgba(0, 0, 0, 0.7)",
				padding: 10,
				titleFont: {
					family: "'Nunito', sans-serif",
					size: 14,
				},
				bodyFont: {
					family: "'Nunito', sans-serif",
					size: 13,
				},
				borderWidth: 1,
				borderColor: "rgba(0, 0, 0, 0.1)",
				displayColors: true,
				boxWidth: 12,
				boxHeight: 12,
				usePointStyle: true,
			},
		},
		scales: {
			x: {
				grid: {
					color: "rgba(0, 0, 0, 0.05)",
					borderDash: [5, 5],
				},
				ticks: {
					font: {
						family: "'Nunito', sans-serif",
						size: 11,
					},
				},
			},
			y: {
				grid: {
					color: "rgba(0, 0, 0, 0.05)",
					borderDash: [5, 5],
				},
				ticks: {
					font: {
						family: "'Nunito', sans-serif",
						size: 11,
					},
					beginAtZero: true,
				},
			},
		},
	};

	// Merge options
	return mergeDeep(defaults, options);
}

/**
 * Create a line chart
 * @param {string} canvasId - Canvas element ID
 * @param {Array} data - Chart data
 * @param {Object} options - Custom options
 * @returns {Object} Chart instance
 */
function createLineChart(canvasId, data, options = {}) {
	const canvas = document.getElementById(canvasId);
	if (!canvas) return null;

	const ctx = canvas.getContext("2d");

	const config = {
		type: "line",
		data: data,
		options: getDefaultChartConfig({
			plugins: {
				title: {
					display: options.title ? true : false,
					text: options.title || "",
					font: {
						family: "'Nunito', sans-serif",
						size: 16,
						weight: "bold",
					},
					padding: {
						top: 10,
						bottom: 20,
					},
				},
			},
			elements: {
				line: {
					tension: 0.4,
				},
				point: {
					radius: 4,
					hoverRadius: 6,
				},
			},
			...options,
		}),
	};

	return new Chart(ctx, config);
}

/**
 * Create a bar chart
 * @param {string} canvasId - Canvas element ID
 * @param {Array} data - Chart data
 * @param {Object} options - Custom options
 * @returns {Object} Chart instance
 */
function createBarChart(canvasId, data, options = {}) {
	const canvas = document.getElementById(canvasId);
	if (!canvas) return null;

	const ctx = canvas.getContext("2d");

	const config = {
		type: "bar",
		data: data,
		options: getDefaultChartConfig({
			plugins: {
				title: {
					display: options.title ? true : false,
					text: options.title || "",
					font: {
						family: "'Nunito', sans-serif",
						size: 16,
						weight: "bold",
					},
					padding: {
						top: 10,
						bottom: 20,
					},
				},
			},
			...options,
		}),
	};

	return new Chart(ctx, config);
}

/**
 * Create a pie chart
 * @param {string} canvasId - Canvas element ID
 * @param {Array} data - Chart data
 * @param {Object} options - Custom options
 * @returns {Object} Chart instance
 */
function createPieChart(canvasId, data, options = {}) {
	const canvas = document.getElementById(canvasId);
	if (!canvas) return null;

	const ctx = canvas.getContext("2d");

	const config = {
		type: "pie",
		data: data,
		options: getDefaultChartConfig({
			plugins: {
				title: {
					display: options.title ? true : false,
					text: options.title || "",
					font: {
						family: "'Nunito', sans-serif",
						size: 16,
						weight: "bold",
					},
					padding: {
						top: 10,
						bottom: 20,
					},
				},
			},
			...options,
		}),
	};

	return new Chart(ctx, config);
}

/**
 * Create a doughnut chart
 * @param {string} canvasId - Canvas element ID
 * @param {Array} data - Chart data
 * @param {Object} options - Custom options
 * @returns {Object} Chart instance
 */
function createDoughnutChart(canvasId, data, options = {}) {
	const canvas = document.getElementById(canvasId);
	if (!canvas) return null;

	const ctx = canvas.getContext("2d");

	const config = {
		type: "doughnut",
		data: data,
		options: getDefaultChartConfig({
			plugins: {
				title: {
					display: options.title ? true : false,
					text: options.title || "",
					font: {
						family: "'Nunito', sans-serif",
						size: 16,
						weight: "bold",
					},
					padding: {
						top: 10,
						bottom: 20,
					},
				},
			},
			cutout: "70%",
			...options,
		}),
	};

	return new Chart(ctx, config);
}

/**
 * Deep merge two objects
 * @param {Object} target - Target object
 * @param {Object} source - Source object
 * @returns {Object} Merged object
 */
function mergeDeep(target, source) {
	const output = Object.assign({}, target);

	if (isObject(target) && isObject(source)) {
		Object.keys(source).forEach((key) => {
			if (isObject(source[key])) {
				if (!(key in target)) {
					Object.assign(output, { [key]: source[key] });
				} else {
					output[key] = mergeDeep(target[key], source[key]);
				}
			} else {
				Object.assign(output, { [key]: source[key] });
			}
		});
	}

	return output;
}

/**
 * Check if value is an object
 * @param {*} item - Value to check
 * @returns {boolean} True if item is an object
 */
function isObject(item) {
	return item && typeof item === "object" && !Array.isArray(item);
}
