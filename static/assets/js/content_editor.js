/**
 * Syllabus Content Editor
 * Manages the interactive editing of syllabus content including topics, units, schedules, and assessments
 */

class SyllabusContentEditor {
	constructor(syllabusId) {
		this.syllabusId = syllabusId;
		this.content = {
			topics: [],
			units: [],
			teaching_schedule: {},
			assessment_plan: {},
		};
		this.autoSaveTimeout = null;
		this.isDirty = false;

		this.initializeEditor();
	}

	initializeEditor() {
		this.bindEvents();
		this.loadContent();
		this.initializeSortable();
		this.setupAutoSave();
	}

	bindEvents() {
		// Tab switching
		document
			.querySelectorAll('#contentTabs button[data-bs-toggle="tab"]')
			.forEach((tab) => {
				tab.addEventListener("shown.bs.tab", (e) => {
					this.handleTabSwitch(e.target.getAttribute("data-bs-target"));
				});
			});

		// Topic management
		document
			.getElementById("addTopicBtn")
			.addEventListener("click", () => this.showAddTopicForm());
		document
			.getElementById("cancelAddTopic")
			.addEventListener("click", () => this.hideAddTopicForm());
		document
			.getElementById("saveNewTopic")
			.addEventListener("click", () => this.addNewTopic());

		// Unit management
		document
			.getElementById("addUnitBtn")
			.addEventListener("click", () => this.addNewUnit());

		// Assessment management
		document
			.getElementById("addAssessmentBtn")
			.addEventListener("click", () => this.addAssessmentMethod());

		// Save button
		document
			.getElementById("saveContentBtn")
			.addEventListener("click", () => this.saveContent());

		// Modal events
		document
			.getElementById("contentEditorModal")
			.addEventListener("hidden.bs.modal", () => {
				this.handleModalClose();
			});
	}

	loadContent() {
		// Simulate loading content from server
		// In real implementation, make AJAX call to get syllabus content
		this.showLoadingState();

		setTimeout(() => {
			// Sample data - replace with actual API call
			this.content = {
				topics: [
					{
						index: 0,
						name: "Introduction to Algebra",
						description: "Basic algebraic concepts and operations",
						duration: 4,
						difficulty: "medium",
						completed: true,
					},
					{
						index: 1,
						name: "Linear Equations",
						description: "Solving linear equations in one variable",
						duration: 6,
						difficulty: "medium",
						completed: false,
					},
					{
						index: 2,
						name: "Quadratic Functions",
						description: "Understanding and graphing quadratic functions",
						duration: 8,
						difficulty: "hard",
						completed: false,
					},
				],
				units: [
					{
						index: 0,
						title: "Algebraic Fundamentals",
						description: "Core algebraic concepts and principles",
						topics: [0, 1],
					},
					{
						index: 1,
						title: "Advanced Functions",
						description: "Complex function types and their applications",
						topics: [2],
					},
				],
				teaching_schedule: {
					weekly_hours: 5,
					total_weeks: 16,
					monthly_plan: [
						{ month: "April", topics: 2, hours: 20 },
						{ month: "May", topics: 3, hours: 25 },
						{ month: "June", topics: 2, hours: 20 },
						{ month: "July", topics: 1, hours: 15 },
					],
				},
				assessment_plan: {
					methods: [
						{ name: "Written Tests", weight: 40, frequency: "Monthly" },
						{ name: "Homework Assignments", weight: 30, frequency: "Weekly" },
						{ name: "Class Participation", weight: 20, frequency: "Daily" },
						{ name: "Project Work", weight: 10, frequency: "Term-end" },
					],
				},
			};

			this.renderContent();
			this.hideLoadingState();
		}, 1000);
	}

	renderContent() {
		this.renderTopics();
		this.renderUnits();
		this.renderSchedule();
		this.renderAssessmentPlan();
	}

	renderTopics() {
		const container = document.getElementById("topicsContainer");
		container.innerHTML = "";

		this.content.topics.forEach((topic, index) => {
			const topicElement = this.createTopicElement(topic, index);
			container.appendChild(topicElement);
		});

		if (this.content.topics.length === 0) {
			container.innerHTML = `
              <div class="text-center py-4 text-muted">
                  <i class="fas fa-list fa-3x mb-3"></i>
                  <p>No topics added yet. Click "Add Topic" to get started.</p>
              </div>
          `;
		}
	}

	createTopicElement(topic, index) {
		const template = document.getElementById("topicItemTemplate");
		const element = template.content.cloneNode(true);
		const topicDiv = element.querySelector(".topic-item");

		topicDiv.setAttribute("data-topic-index", index);

		// Set values
		element.querySelector(".topic-name").value = topic.name || "";
		element.querySelector(".topic-description").value = topic.description || "";
		element.querySelector(".topic-duration").value = topic.duration || "";
		element.querySelector(".topic-difficulty").value =
			topic.difficulty || "medium";

		// Set status badge
		const statusBadge = element.querySelector(".topic-status");
		if (topic.completed) {
			statusBadge.className = "badge bg-success";
			statusBadge.textContent = "Completed";
			topicDiv.classList.add("completed");
		} else {
			statusBadge.className = "badge bg-secondary";
			statusBadge.textContent = "Pending";
		}

		// Bind events
		this.bindTopicEvents(element);

		return element;
	}

	bindTopicEvents(element) {
		// Auto-save on input changes
		element.querySelectorAll("input, textarea, select").forEach((input) => {
			input.addEventListener("input", () => {
				this.markDirty();
				this.triggerAutoSave();
			});
		});

		// Complete topic button
		element.querySelector(".complete-topic").addEventListener("click", (e) => {
			const topicIndex = parseInt(
				e.target.closest(".topic-item").getAttribute("data-topic-index")
			);
			this.toggleTopicCompletion(topicIndex);
		});

		// Delete topic button
		element.querySelector(".delete-topic").addEventListener("click", (e) => {
			const topicIndex = parseInt(
				e.target.closest(".topic-item").getAttribute("data-topic-index")
			);
			this.deleteTopic(topicIndex);
		});
	}

	renderUnits() {
		const container = document.getElementById("unitsContainer");
		container.innerHTML = "";

		this.content.units.forEach((unit, index) => {
			const unitElement = this.createUnitElement(unit, index);
			container.appendChild(unitElement);
		});

		if (this.content.units.length === 0) {
			container.innerHTML = `
              <div class="text-center py-4 text-muted">
                  <i class="fas fa-layer-group fa-3x mb-3"></i>
                  <p>No units created yet. Units help organize related topics together.</p>
              </div>
          `;
		}
	}

	createUnitElement(unit, index) {
		const template = document.getElementById("unitItemTemplate");
		const element = template.content.cloneNode(true);
		const unitDiv = element.querySelector(".unit-item");

		unitDiv.setAttribute("data-unit-index", index);

		// Set values
		element.querySelector(".unit-title").value = unit.title || "";
		element.querySelector(".unit-description").value = unit.description || "";

		// Render assigned topics
		const topicsContainer = element.querySelector(".unit-topics-list");
		if (unit.topics && unit.topics.length > 0) {
			unit.topics.forEach((topicIndex) => {
				const topic = this.content.topics[topicIndex];
				if (topic) {
					const topicTag = document.createElement("span");
					topicTag.className = "badge bg-primary me-2 mb-2";
					topicTag.innerHTML = `${topic.name} <i class="fas fa-times ms-1 remove-topic" data-topic-index="${topicIndex}"></i>`;
					topicsContainer.appendChild(topicTag);
				}
			});
		} else {
			topicsContainer.innerHTML =
				'<em class="text-muted">No topics assigned</em>';
		}

		// Bind events
		this.bindUnitEvents(element);

		return element;
	}

	bindUnitEvents(element) {
		// Auto-save on input changes
		element.querySelectorAll("input, textarea").forEach((input) => {
			input.addEventListener("input", () => {
				this.markDirty();
				this.triggerAutoSave();
			});
		});

		// Delete unit button
		element.querySelector(".delete-unit").addEventListener("click", (e) => {
			const unitIndex = parseInt(
				e.target.closest(".unit-item").getAttribute("data-unit-index")
			);
			this.deleteUnit(unitIndex);
		});

		// Assign topics button
		element
			.querySelector(".assign-topics-btn")
			.addEventListener("click", (e) => {
				const unitIndex = parseInt(
					e.target.closest(".unit-item").getAttribute("data-unit-index")
				);
				this.showTopicAssignmentModal(unitIndex);
			});

		// Remove topic from unit
		element.querySelectorAll(".remove-topic").forEach((removeBtn) => {
			removeBtn.addEventListener("click", (e) => {
				const unitIndex = parseInt(
					e.target.closest(".unit-item").getAttribute("data-unit-index")
				);
				const topicIndex = parseInt(e.target.getAttribute("data-topic-index"));
				this.removeTopicFromUnit(unitIndex, topicIndex);
			});
		});
	}

	renderSchedule() {
		// Render weekly schedule chart
		this.renderWeeklyScheduleChart();

		// Render monthly plan table
		const monthlyPlanBody = document.getElementById("monthlyPlanBody");
		monthlyPlanBody.innerHTML = "";

		if (this.content.teaching_schedule.monthly_plan) {
			this.content.teaching_schedule.monthly_plan.forEach((month) => {
				const row = document.createElement("tr");
				row.innerHTML = `
                  <td>${month.month}</td>
                  <td>${month.topics}</td>
                  <td>${month.hours}</td>
              `;
				monthlyPlanBody.appendChild(row);
			});
		}
	}

	renderWeeklyScheduleChart() {
		// Sample weekly schedule data
		const weeklyData = [
			{ day: "Monday", hours: 1 },
			{ day: "Tuesday", hours: 1.5 },
			{ day: "Wednesday", hours: 1 },
			{ day: "Thursday", hours: 1.5 },
			{ day: "Friday", hours: 1 },
		];

		const options = {
			series: [
				{
					name: "Teaching Hours",
					data: weeklyData.map((d) => d.hours),
				},
			],
			chart: {
				type: "bar",
				height: 200,
				toolbar: { show: false },
			},
			xaxis: {
				categories: weeklyData.map((d) => d.day),
			},
			yaxis: {
				title: { text: "Hours" },
			},
			colors: ["#007bff"],
			dataLabels: {
				enabled: true,
				formatter: function (val) {
					return val + "h";
				},
			},
		};

		const chart = new ApexCharts(
			document.querySelector("#weeklyScheduleChart"),
			options
		);
		chart.render();
	}

	renderAssessmentPlan() {
		const container = document.getElementById("assessmentMethodsContainer");
		container.innerHTML = "";

		if (this.content.assessment_plan.methods) {
			this.content.assessment_plan.methods.forEach((method, index) => {
				const methodElement = this.createAssessmentMethodElement(method, index);
				container.appendChild(methodElement);
			});
		}

		if (this.content.assessment_plan.methods.length === 0) {
			container.innerHTML = `
              <div class="text-center py-3 text-muted">
                  <p>No assessment methods defined yet.</p>
              </div>
          `;
		}
	}

	createAssessmentMethodElement(method, index) {
		const div = document.createElement("div");
		div.className = "card mb-2";
		div.innerHTML = `
          <div class="card-body">
              <div class="row align-items-center">
                  <div class="col-md-3">
                      <input type="text" class="form-control form-control-sm" value="${
												method.name
											}" placeholder="Method name">
                  </div>
                  <div class="col-md-2">
                      <div class="input-group input-group-sm">
                          <input type="number" class="form-control" value="${
														method.weight
													}" min="0" max="100">
                          <span class="input-group-text">%</span>
                      </div>
                  </div>
                  <div class="col-md-3">
                      <select class="form-select form-select-sm">
                          <option value="daily" ${
														method.frequency === "Daily" ? "selected" : ""
													}>Daily</option>
                          <option value="weekly" ${
														method.frequency === "Weekly" ? "selected" : ""
													}>Weekly</option>
                          <option value="monthly" ${
														method.frequency === "Monthly" ? "selected" : ""
													}>Monthly</option>
                          <option value="term-end" ${
														method.frequency === "Term-end" ? "selected" : ""
													}>Term-end</option>
                      </select>
                  </div>
                  <div class="col-md-3">
                      <div class="progress" style="height: 8px;">
                          <div class="progress-bar" style="width: ${
														method.weight
													}%"></div>
                      </div>
                  </div>
                  <div class="col-md-1">
                      <button type="button" class="btn btn-outline-danger btn-sm delete-assessment" data-index="${index}">
                          <i class="fas fa-trash"></i>
                      </button>
                  </div>
              </div>
          </div>
      `;

		// Bind events
		div.querySelectorAll("input, select").forEach((input) => {
			input.addEventListener("input", () => {
				this.markDirty();
				this.triggerAutoSave();
			});
		});

		div.querySelector(".delete-assessment").addEventListener("click", () => {
			this.deleteAssessmentMethod(index);
		});

		return div;
	}

	// Topic management methods
	showAddTopicForm() {
		document.getElementById("addTopicForm").classList.remove("d-none");
		document.getElementById("newTopicName").focus();
	}

	hideAddTopicForm() {
		document.getElementById("addTopicForm").classList.add("d-none");
		this.clearAddTopicForm();
	}

	clearAddTopicForm() {
		document.getElementById("newTopicName").value = "";
		document.getElementById("newTopicDescription").value = "";
		document.getElementById("newTopicDuration").value = "";
		document.getElementById("newTopicDifficulty").value = "medium";
	}

	addNewTopic() {
		const name = document.getElementById("newTopicName").value.trim();
		const description = document
			.getElementById("newTopicDescription")
			.value.trim();
		const duration =
			parseFloat(document.getElementById("newTopicDuration").value) || 0;
		const difficulty = document.getElementById("newTopicDifficulty").value;

		if (!name) {
			alert("Please enter a topic name.");
			return;
		}

		const newTopic = {
			index: this.content.topics.length,
			name: name,
			description: description,
			duration: duration,
			difficulty: difficulty,
			completed: false,
		};

		this.content.topics.push(newTopic);
		this.renderTopics();
		this.hideAddTopicForm();
		this.markDirty();
		this.showAutoSaveIndicator();
	}

	toggleTopicCompletion(topicIndex) {
		if (this.content.topics[topicIndex]) {
			this.content.topics[topicIndex].completed =
				!this.content.topics[topicIndex].completed;
			this.renderTopics();
			this.markDirty();
		}
	}

	deleteTopic(topicIndex) {
		if (confirm("Are you sure you want to delete this topic?")) {
			this.content.topics.splice(topicIndex, 1);
			// Update topic indices
			this.content.topics.forEach((topic, index) => {
				topic.index = index;
			});
			this.renderTopics();
			this.renderUnits(); // Re-render units to update topic assignments
			this.markDirty();
		}
	}

	// Unit management methods
	addNewUnit() {
		const newUnit = {
			index: this.content.units.length,
			title: "New Unit",
			description: "",
			topics: [],
		};

		this.content.units.push(newUnit);
		this.renderUnits();
		this.markDirty();
	}

	deleteUnit(unitIndex) {
		if (confirm("Are you sure you want to delete this unit?")) {
			this.content.units.splice(unitIndex, 1);
			// Update unit indices
			this.content.units.forEach((unit, index) => {
				unit.index = index;
			});
			this.renderUnits();
			this.markDirty();
		}
	}

	removeTopicFromUnit(unitIndex, topicIndex) {
		if (this.content.units[unitIndex]) {
			const topics = this.content.units[unitIndex].topics;
			const index = topics.indexOf(topicIndex);
			if (index > -1) {
				topics.splice(index, 1);
				this.renderUnits();
				this.markDirty();
			}
		}
	}

	// Assessment management methods
	addAssessmentMethod() {
		const newMethod = {
			name: "New Assessment Method",
			weight: 10,
			frequency: "Weekly",
		};

		if (!this.content.assessment_plan.methods) {
			this.content.assessment_plan.methods = [];
		}

		this.content.assessment_plan.methods.push(newMethod);
		this.renderAssessmentPlan();
		this.markDirty();
	}

	deleteAssessmentMethod(index) {
		if (confirm("Are you sure you want to delete this assessment method?")) {
			this.content.assessment_plan.methods.splice(index, 1);
			this.renderAssessmentPlan();
			this.markDirty();
		}
	}

	// Utility methods
	initializeSortable() {
		// Initialize sortable for topics (using SortableJS if available)
		if (typeof Sortable !== "undefined") {
			const topicsContainer = document.getElementById("topicsContainer");
			new Sortable(topicsContainer, {
				handle: ".drag-handle",
				animation: 150,
				ghostClass: "sortable-ghost",
				chosenClass: "sortable-chosen",
				onEnd: (evt) => {
					this.reorderTopics(evt.oldIndex, evt.newIndex);
				},
			});
		}
	}

	reorderTopics(oldIndex, newIndex) {
		const topic = this.content.topics.splice(oldIndex, 1)[0];
		this.content.topics.splice(newIndex, 0, topic);

		// Update indices
		this.content.topics.forEach((topic, index) => {
			topic.index = index;
		});

		this.markDirty();
	}

	setupAutoSave() {
		this.autoSaveInterval = setInterval(() => {
			if (this.isDirty) {
				this.autoSave();
			}
		}, 30000); // Auto-save every 30 seconds
	}

	triggerAutoSave() {
		clearTimeout(this.autoSaveTimeout);
		this.autoSaveTimeout = setTimeout(() => {
			this.autoSave();
		}, 3000); // Auto-save 3 seconds after last change
	}

	autoSave() {
		if (!this.isDirty) return;

		// Simulate API call to save content
		console.log("Auto-saving content...", this.content);

		this.showAutoSaveIndicator();
		this.isDirty = false;
	}

	saveContent() {
		// Show saving state
		const saveBtn = document.getElementById("saveContentBtn");
		const originalText = saveBtn.innerHTML;
		saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Saving...';
		saveBtn.disabled = true;

		// Simulate API call to save content
		setTimeout(() => {
			console.log("Saving content...", this.content);

			// Reset button
			saveBtn.innerHTML = originalText;
			saveBtn.disabled = false;

			// Show success message
			this.showAutoSaveIndicator("Changes saved successfully!");
			this.isDirty = false;
		}, 1000);
	}

	showAutoSaveIndicator(message = "Auto-saved") {
		const indicator = document.getElementById("autoSaveIndicator");
		indicator.textContent = message;
		indicator.classList.remove("d-none");

		setTimeout(() => {
			indicator.classList.add("d-none");
		}, 3000);
	}

	markDirty() {
		this.isDirty = true;
	}

	showLoadingState() {
		const tabContents = document.querySelectorAll(".tab-pane");
		tabContents.forEach((pane) => {
			pane.innerHTML = `
              <div class="text-center py-5">
                  <div class="spinner-border text-primary" role="status">
                      <span class="visually-hidden">Loading...</span>
                  </div>
                  <p class="mt-2 text-muted">Loading content...</p>
              </div>
          `;
		});
	}

	hideLoadingState() {
		// Content will be rendered by renderContent()
	}

	handleTabSwitch(targetPane) {
		// Perform any tab-specific initialization
		if (targetPane === "#schedule-pane") {
			// Re-render charts when schedule tab is shown
			setTimeout(() => {
				this.renderWeeklyScheduleChart();
			}, 100);
		}
	}

	handleModalClose() {
		if (this.isDirty) {
			if (
				confirm("You have unsaved changes. Do you want to save before closing?")
			) {
				this.saveContent();
			}
		}

		// Clear auto-save interval
		if (this.autoSaveInterval) {
			clearInterval(this.autoSaveInterval);
		}
	}

	// Public API methods
	static openEditor(syllabusId) {
		const modal = new bootstrap.Modal(
			document.getElementById("contentEditorModal")
		);
		const editor = new SyllabusContentEditor(syllabusId);
		modal.show();
		return editor;
	}
}

// Global function to open content editor
window.openContentEditor = function (syllabusId) {
	return SyllabusContentEditor.openEditor(syllabusId);
};

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
	// Content editor will be initialized when modal is opened
	console.log("Syllabus Content Editor loaded");
});
