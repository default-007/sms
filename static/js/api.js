/**
 * API interaction functions for the School Management System
 */

/**
 * Base API URL
 */
const API_BASE_URL = "/api/v1";

/**
 * Generic fetch API wrapper with authentication
 * @param {string} endpoint - API endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} Response data
 */
async function fetchAPI(endpoint, options = {}) {
	const url = `${API_BASE_URL}${endpoint}`;

	// Default options
	const defaultOptions = {
		headers: {
			"Content-Type": "application/json",
			"X-CSRFToken": getCsrfToken(),
		},
		credentials: "same-origin",
	};

	// Merge options
	const fetchOptions = {
		...defaultOptions,
		...options,
		headers: {
			...defaultOptions.headers,
			...options.headers,
		},
	};

	try {
		const response = await fetch(url, fetchOptions);

		// Handle HTTP errors
		if (!response.ok) {
			const errorData = await response.json().catch(() => ({}));
			throw new APIError(
				`API Error: ${response.status} ${response.statusText}`,
				response.status,
				errorData
			);
		}

		// Handle empty response
		const contentType = response.headers.get("content-type");
		if (contentType && contentType.includes("application/json")) {
			return await response.json();
		}

		return await response.text();
	} catch (error) {
		console.error("API Request Failed:", error);
		throw error;
	}
}

/**
 * Custom API Error class
 */
class APIError extends Error {
	constructor(message, status, data = {}) {
		super(message);
		this.name = "APIError";
		this.status = status;
		this.data = data;
	}
}

/**
 * GET request wrapper
 * @param {string} endpoint - API endpoint
 * @param {Object} params - Query parameters
 * @returns {Promise<Object>} Response data
 */
async function getAPI(endpoint, params = {}) {
	// Convert params to query string
	const queryParams = new URLSearchParams();

	Object.keys(params).forEach((key) => {
		if (
			params[key] !== null &&
			params[key] !== undefined &&
			params[key] !== ""
		) {
			queryParams.append(key, params[key]);
		}
	});

	const queryString = queryParams.toString();
	const url = queryString ? `${endpoint}?${queryString}` : endpoint;

	return fetchAPI(url, { method: "GET" });
}

/**
 * POST request wrapper
 * @param {string} endpoint - API endpoint
 * @param {Object} data - Request body data
 * @returns {Promise<Object>} Response data
 */
async function postAPI(endpoint, data = {}) {
	return fetchAPI(endpoint, {
		method: "POST",
		body: JSON.stringify(data),
	});
}

/**
 * PUT request wrapper
 * @param {string} endpoint - API endpoint
 * @param {Object} data - Request body data
 * @returns {Promise<Object>} Response data
 */
async function putAPI(endpoint, data = {}) {
	return fetchAPI(endpoint, {
		method: "PUT",
		body: JSON.stringify(data),
	});
}

/**
 * PATCH request wrapper
 * @param {string} endpoint - API endpoint
 * @param {Object} data - Request body data
 * @returns {Promise<Object>} Response data
 */
async function patchAPI(endpoint, data = {}) {
	return fetchAPI(endpoint, {
		method: "PATCH",
		body: JSON.stringify(data),
	});
}

/**
 * DELETE request wrapper
 * @param {string} endpoint - API endpoint
 * @returns {Promise<Object>} Response data
 */
async function deleteAPI(endpoint) {
	return fetchAPI(endpoint, { method: "DELETE" });
}

/**
 * Upload file to API
 * @param {string} endpoint - API endpoint
 * @param {File|FormData} file - File to upload or FormData with files
 * @param {Object} data - Additional form data
 * @returns {Promise<Object>} Response data
 */
async function uploadAPI(endpoint, file, data = {}) {
	let formData;

	if (file instanceof FormData) {
		formData = file;

		// Add additional data to FormData
		Object.keys(data).forEach((key) => {
			formData.append(key, data[key]);
		});
	} else {
		formData = new FormData();
		formData.append("file", file);

		// Add additional data to FormData
		Object.keys(data).forEach((key) => {
			formData.append(key, data[key]);
		});
	}

	return fetchAPI(endpoint, {
		method: "POST",
		headers: {
			"X-CSRFToken": getCsrfToken(),
			// Note: Don't set Content-Type here, let the browser set it with the boundary
		},
		body: formData,
	});
}
