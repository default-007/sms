// static/teachers/js/teacher-forms.js
/**
 * JavaScript for enhanced teacher form functionality
 */

// Validate teacher form before submission
function validateTeacherForm() {
	let isValid = true;
	const requiredFields = document.querySelectorAll("[required]");

	// Reset error states
	document.querySelectorAll(".is-invalid").forEach((el) => {
		el.classList.remove("is-invalid");
	});

	// Check required fields
	requiredFields.forEach((field) => {
		if (!field.value.trim()) {
			field.classList.add("is-invalid");
			isValid = false;
		}
	});

	// Email validation
	const emailField = document.getElementById("id_email");
	if (emailField && emailField.value) {
		const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		if (!emailRegex.test(emailField.value)) {
			emailField.classList.add("is-invalid");
			isValid = false;
		}
	}

	// Phone number validation
	const phoneField = document.getElementById("id_phone_number");
	if (phoneField && phoneField.value) {
		const phoneRegex = /^[0-9+\-\s()]{6,20}$/;
		if (!phoneRegex.test(phoneField.value)) {
			phoneField.classList.add("is-invalid");
			isValid = false;
		}
	}

	// Salary validation
	const salaryField = document.getElementById("id_salary");
	if (salaryField && salaryField.value) {
		if (isNaN(salaryField.value) || parseFloat(salaryField.value) <= 0) {
			salaryField.classList.add("is-invalid");
			isValid = false;
		}
	}

	return isValid;
}

// Initialize form validation
document.addEventListener("DOMContentLoaded", function () {
	const teacherForm = document.getElementById("teacher-form");
	if (teacherForm) {
		teacherForm.addEventListener("submit", function (event) {
			if (!validateTeacherForm()) {
				event.preventDefault();
				// Scroll to the first error
				const firstError = document.querySelector(".is-invalid");
				if (firstError) {
					firstError.scrollIntoView({ behavior: "smooth", block: "center" });
					firstError.focus();
				}
			}
		});
	}

	// Initialize any Select2 dropdowns for enhanced select boxes
	if (typeof $.fn.select2 !== "undefined") {
		$(".select2-enable").select2({
			theme: "bootstrap-5",
			width: "100%",
		});
	}

	// Initialize evaluation form if it exists
	initEvaluationForm();
});

// Dynamic criteria management for teacher evaluations
function initEvaluationForm() {
	const criteriaContainer = document.getElementById("criteria-container");
	const criteriaInput = document.getElementById("id_criteria");

	if (criteriaContainer && criteriaInput) {
		try {
			renderCriteriaFields();

			// Add new criterion button
			const addButton = document.createElement("button");
			addButton.type = "button";
			addButton.className = "btn btn-outline-primary mt-3";
			addButton.innerHTML = '<i class="fas fa-plus"></i> Add Criterion';
			addButton.onclick = addNewCriterion;
			criteriaContainer.parentNode.appendChild(addButton);
		} catch (e) {
			console.error("Error initializing evaluation form:", e);
		}
	}
}

// Add a new custom criterion to the evaluation
function addNewCriterion() {
	const criteriaInput = document.getElementById("id_criteria");
	let criteriaData = {};

	try {
		criteriaData = JSON.parse(criteriaInput.value);
	} catch (e) {
		criteriaData = {};
	}

	// Generate a unique key for the new criterion
	const timestamp = new Date().getTime();
	const newKey = `custom_criterion_${timestamp}`;

	// Add the new criterion to the data
	criteriaData[newKey] = {
		score: 0,
		max_score: 10,
		comments: "",
		name: "Custom Criterion",
	};

	// Update the hidden input
	criteriaInput.value = JSON.stringify(criteriaData);

	// Re-render the criteria fields
	renderCriteriaFields();
}

function renderCriteriaFields() {
	const criteriaContainer = document.getElementById("criteria-container");
	const criteriaInput = document.getElementById("id_criteria");
	let criteriaData = {};

	try {
		criteriaData = JSON.parse(criteriaInput.value);
	} catch (e) {
		criteriaData = {
			teaching_methodology: { score: 0, max_score: 10, comments: "" },
			subject_knowledge: { score: 0, max_score: 10, comments: "" },
			classroom_management: { score: 0, max_score: 10, comments: "" },
			student_engagement: { score: 0, max_score: 10, comments: "" },
			professional_conduct: { score: 0, max_score: 10, comments: "" },
		};
	}

	// Clear container
	criteriaContainer.innerHTML = "";

	// Create fields for each criterion
	Object.keys(criteriaData).forEach((criterion) => {
		const data = criteriaData[criterion];
		const criterionDiv = document.createElement("div");
		criterionDiv.className = "col-12 mb-3";

		const criterionName = criterion
			.split("_")
			.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
			.join(" ");

		criterionDiv.innerHTML = `
          <div class="card">
              <div class="card-header bg-light">
                  <h6 class="mb-0">${data.name || criterionName}</h6>
              </div>
              <div class="card-body">
                  <div class="row">
                      <div class="col-md-3 mb-3">
                          <label class="form-label">Score</label>
                          <input type="number" class="form-control" 
                              id="score_${criterion}" name="score_${criterion}"
                              min="0" max="${data.max_score}" value="${
			data.score || 0
		}"
                              onchange="updateCriteria()">
                          <div class="form-text">Max: ${
														data.max_score || 10
													}</div>
                      </div>
                      <div class="col-md-9 mb-3">
                          <label class="form-label">Comments</label>
                          <textarea class="form-control" id="comments_${criterion}" 
                                  name="comments_${criterion}" rows="2"
                                  onchange="updateCriteria()">${
																		data.comments || ""
																	}</textarea>
                      </div>
                  </div>
              </div>
          </div>
      `;

		criteriaContainer.appendChild(criterionDiv);
	});

	criteriaInput.value = JSON.stringify(criteriaData);
}

function updateCriteria() {
	const criteriaInput = document.getElementById("id_criteria");
	let criteriaData = {};

	try {
		criteriaData = JSON.parse(criteriaInput.value);
	} catch (e) {
		criteriaData = {};
	}

	// Update values from form
	Object.keys(criteriaData).forEach((criterion) => {
		const scoreInput = document.getElementById(`score_${criterion}`);
		const commentsInput = document.getElementById(`comments_${criterion}`);

		if (scoreInput && commentsInput) {
			criteriaData[criterion].score = parseInt(scoreInput.value) || 0;
			criteriaData[criterion].comments = commentsInput.value;
		}
	});

	// Update hidden input
	criteriaInput.value = JSON.stringify(criteriaData);

	// Calculate total score
	let totalScore = 0;
	let maxScore = 0;

	Object.values(criteriaData).forEach((data) => {
		totalScore += parseInt(data.score) || 0;
		maxScore += parseInt(data.max_score) || 0;
	});

	// Update score field
	const scoreField = document.getElementById("id_score");
	if (scoreField) {
		scoreField.value =
			maxScore > 0 ? ((totalScore / maxScore) * 100).toFixed(2) : 0;
	}
}
