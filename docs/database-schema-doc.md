# School Management System - Database Schema

## User Management

### User

- `id` (Primary Key)
- `username` (Unique)
- `email` (Unique)
- `password` (Hashed)
- `first_name`
- `last_name`
- `phone_number`
- `address`
- `date_of_birth`
- `gender`
- `profile_picture`
- `is_active`
- `date_joined`
- `last_login`

**Relationships:** One-to-Many with Student, Teacher, Parent

### UserRole

- `id` (Primary Key)
- `name` (e.g., Admin, Teacher, Parent, Staff)
- `description`
- `permissions` (JSON field storing permission details)

**Relationships:** One-to-Many with UserRoleAssignment

### UserRoleAssignment

- `id` (Primary Key)
- `user_id` (Foreign Key to User) **Many-to-One**
- `role_id` (Foreign Key to UserRole) **Many-to-One**
- `assigned_date`
- `assigned_by` (Foreign Key to User) **Many-to-One**

## Student Management

### Student

- `id` (Primary Key)
- `user_id` (Foreign Key to User) **One-to-One**
- `admission_number` (Unique)
- `admission_date`
- `current_class_id` (Foreign Key to Class) **Many-to-One**
- `roll_number`
- `blood_group`
- `medical_conditions`
- `emergency_contact_name`
- `emergency_contact_number`
- `previous_school`
- `status` (Active, Inactive, Graduated, etc.)

**Relationships:** One-to-Many with Attendance, StudentExamResult, AssignmentSubmission

### Parent

- `id` (Primary Key)
- `user_id` (Foreign Key to User) **One-to-One**
- `occupation`
- `annual_income`
- `education`

**Relationships:** Many-to-Many with Student (through StudentParentRelation)

### StudentParentRelation

- `id` (Primary Key)
- `student_id` (Foreign Key to Student) **Many-to-One**
- `parent_id` (Foreign Key to Parent) **Many-to-One**
- `relation_type` (Father, Mother, Guardian)
- `is_primary_contact` (Boolean)

### Attendance

- `id` (Primary Key)
- `student_id` (Foreign Key to Student) **Many-to-One**
- `class_id` (Foreign Key to Class) **Many-to-One**
- `subject_id` (Foreign Key to Subject) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `date`
- `status` (Present, Absent, Late, Excused)
- `remarks`
- `marked_by` (Foreign Key to User) **Many-to-One**
- `marked_at` (Timestamp)

## Teacher Management

### Teacher

- `id` (Primary Key)
- `user_id` (Foreign Key to User) **One-to-One**
- `employee_id` (Unique)
- `joining_date`
- `qualification`
- `experience_years`
- `specialization`
- `department_id` (Foreign Key to Department) **Many-to-One**
- `position`
- `salary`
- `contract_type` (Permanent, Temporary, Contract)
- `status` (Active, On Leave, Terminated)

**Relationships:** One-to-Many with TeacherClassAssignment, TeacherEvaluation

### TeacherClassAssignment

- `id` (Primary Key)
- `teacher_id` (Foreign Key to Teacher) **Many-to-One**
- `class_id` (Foreign Key to Class) **Many-to-One**
- `subject_id` (Foreign Key to Subject) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `is_class_teacher` (Boolean)

### TeacherEvaluation

- `id` (Primary Key)
- `teacher_id` (Foreign Key to Teacher) **Many-to-One**
- `evaluator_id` (Foreign Key to User) **Many-to-One**
- `evaluation_date`
- `criteria` (JSON field for evaluation parameters)
- `score`
- `remarks`
- `followup_actions`

## Academic Structure (Split from Courses)

### Department

- `id` (Primary Key)
- `name`
- `description`
- `head_id` (Foreign Key to Teacher) **One-to-One**
- `creation_date`

**Relationships:** One-to-Many with Teacher, Subject, Grade

### AcademicYear

- `id` (Primary Key)
- `name` (e.g., "2023-2024")
- `start_date`
- `end_date`
- `is_current` (Boolean)

**Relationships:** One-to-Many with Term, Class, Exam

### Term

- `id` (Primary Key)
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `name` (e.g., "First Term", "Second Term", "Third Term")
- `term_number` (1, 2, 3)
- `start_date`
- `end_date`
- `is_current` (Boolean)

**Relationships:** One-to-Many with FeeStructure, Invoice, Attendance, StudentExamResult

### Grade

- `id` (Primary Key)
- `name` (e.g., "Grade 1", "Grade 2")
- `description`
- `department_id` (Foreign Key to Department) **Many-to-One**
- `order_sequence`

**Relationships:** One-to-Many with Class, FeeStructure

### Section

- `id` (Primary Key)
- `name` (e.g., "A", "B", "C")
- `description`

**Relationships:** One-to-Many with Class, FeeStructure

### Class

- `id` (Primary Key)
- `grade_id` (Foreign Key to Grade) **Many-to-One**
- `section_id` (Foreign Key to Section) **Many-to-One**
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `room_number`
- `capacity`
- `class_teacher_id` (Foreign Key to Teacher) **Many-to-One**

**Relationships:** One-to-Many with Student, Attendance, TeacherClassAssignment, SpecialFee

## Subjects Module

### Subject

- `id` (Primary Key)
- `name`
- `code` (Unique)
- `description`
- `department_id` (Foreign Key to Department) **Many-to-One**
- `credit_hours`
- `is_elective` (Boolean)
- `grade_level` (Which grades can take this subject)

**Relationships:** One-to-Many with Syllabus, TeacherClassAssignment, Assignment

### Syllabus

- `id` (Primary Key)
- `subject_id` (Foreign Key to Subject) **Many-to-One**
- `grade_id` (Foreign Key to Grade) **Many-to-One**
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `title`
- `description`
- `content` (JSON field storing syllabus structure)
- `learning_objectives` (JSON array)
- `completion_percentage`
- `created_by` (Foreign Key to User) **Many-to-One**
- `last_updated_by` (Foreign Key to User) **Many-to-One**
- `last_updated_at` (Timestamp)

## Scheduling Module

### TimeSlot

- `id` (Primary Key)
- `day_of_week`
- `start_time`
- `end_time`
- `duration_minutes`
- `period_number`

**Relationships:** One-to-Many with Timetable

### Timetable

- `id` (Primary Key)
- `class_id` (Foreign Key to Class) **Many-to-One**
- `subject_id` (Foreign Key to Subject) **Many-to-One**
- `teacher_id` (Foreign Key to Teacher) **Many-to-One**
- `time_slot_id` (Foreign Key to TimeSlot) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `room`
- `effective_from_date`
- `effective_to_date`
- `is_active` (Boolean)

## Assignments Module

### Assignment

- `id` (Primary Key)
- `title`
- `description`
- `class_id` (Foreign Key to Class) **Many-to-One**
- `subject_id` (Foreign Key to Subject) **Many-to-One**
- `teacher_id` (Foreign Key to Teacher) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `assigned_date`
- `due_date`
- `total_marks`
- `attachment` (File path or URL)
- `submission_type` (Online, Physical)
- `status` (Draft, Published, Closed)

**Relationships:** One-to-Many with AssignmentSubmission

### AssignmentSubmission

- `id` (Primary Key)
- `assignment_id` (Foreign Key to Assignment) **Many-to-One**
- `student_id` (Foreign Key to Student) **Many-to-One**
- `submission_date`
- `content` (Text or File path)
- `remarks`
- `marks_obtained`
- `status` (Submitted, Late, Graded)
- `graded_by` (Foreign Key to Teacher) **Many-to-One**
- `graded_at` (Timestamp)

## Exams & Assessments

### ExamType

- `id` (Primary Key)
- `name` (e.g., Mid-term, Final, Quiz, Continuous Assessment)
- `description`
- `contribution_percentage`
- `is_term_based` (Boolean)

**Relationships:** One-to-Many with Exam

### Exam

- `id` (Primary Key)
- `name`
- `exam_type_id` (Foreign Key to ExamType) **Many-to-One**
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `start_date`
- `end_date`
- `description`
- `created_by` (Foreign Key to User) **Many-to-One**
- `status` (Scheduled, Ongoing, Completed, Cancelled)

**Relationships:** One-to-Many with ExamSchedule

### ExamSchedule

- `id` (Primary Key)
- `exam_id` (Foreign Key to Exam) **Many-to-One**
- `class_id` (Foreign Key to Class) **Many-to-One**
- `subject_id` (Foreign Key to Subject) **Many-to-One**
- `date`
- `start_time`
- `end_time`
- `room`
- `supervisor_id` (Foreign Key to Teacher) **Many-to-One**
- `total_marks`
- `passing_marks`

**Relationships:** One-to-Many with StudentExamResult

### StudentExamResult

- `id` (Primary Key)
- `student_id` (Foreign Key to Student) **Many-to-One**
- `exam_schedule_id` (Foreign Key to ExamSchedule) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `marks_obtained`
- `percentage`
- `grade`
- `remarks`
- `is_pass` (Boolean)
- `entered_by` (Foreign Key to User) **Many-to-One**
- `entry_date` (Timestamp)

### GradingSystem

- `id` (Primary Key)
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `grade_name` (e.g., A, B, C)
- `min_percentage`
- `max_percentage`
- `grade_point`
- `description`

### ReportCard

- `id` (Primary Key)
- `student_id` (Foreign Key to Student) **Many-to-One**
- `class_id` (Foreign Key to Class) **Many-to-One**
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `generation_date`
- `total_marks`
- `marks_obtained`
- `percentage`
- `grade`
- `grade_point_average`
- `remarks`
- `attendance_percentage`
- `class_teacher_remarks`
- `principal_remarks`
- `status` (Draft, Published, Archived)

## Fee & Finance Management

### FeeCategory

- `id` (Primary Key)
- `name` (e.g., Tuition, Transport, Library, Laboratory)
- `description`
- `is_recurring` (Boolean)
- `frequency` (Monthly, Termly, Annually)
- `is_mandatory` (Boolean)

**Relationships:** One-to-Many with FeeStructure, SpecialFee

### FeeStructure

- `id` (Primary Key)
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `section_id` (Foreign Key to Section) **Many-to-One** (Optional)
- `grade_id` (Foreign Key to Grade) **Many-to-One** (Optional)
- `fee_category_id` (Foreign Key to FeeCategory) **Many-to-One**
- `amount`
- `due_date`
- `late_fee_percentage`
- `grace_period_days`
- `is_active` (Boolean)

**Relationships:** One-to-Many with InvoiceItem

### SpecialFee

- `id` (Primary Key)
- `name`
- `description`
- `fee_category_id` (Foreign Key to FeeCategory) **Many-to-One**
- `amount`
- `fee_type` (Class-based, Student-specific)
- `class_id` (Foreign Key to Class) **Many-to-One** (Optional)
- `student_id` (Foreign Key to Student) **Many-to-One** (Optional)
- `term_id` (Foreign Key to Term) **Many-to-One**
- `due_date`
- `reason`
- `created_by` (Foreign Key to User) **Many-to-One**
- `is_active` (Boolean)

**Relationships:** One-to-Many with InvoiceItem

### Scholarship

- `id` (Primary Key)
- `name`
- `description`
- `discount_type` (Percentage, Fixed Amount)
- `discount_value`
- `criteria` (Merit, Need-based, etc.)
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `applicable_terms` (JSON array of term IDs)
- `max_recipients`
- `is_active` (Boolean)

**Relationships:** One-to-Many with StudentScholarship

### StudentScholarship

- `id` (Primary Key)
- `student_id` (Foreign Key to Student) **Many-to-One**
- `scholarship_id` (Foreign Key to Scholarship) **Many-to-One**
- `approved_by` (Foreign Key to User) **Many-to-One**
- `approval_date`
- `start_date`
- `end_date`
- `remarks`
- `status` (Approved, Suspended, Terminated)

### Invoice

- `id` (Primary Key)
- `student_id` (Foreign Key to Student) **Many-to-One**
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `invoice_number` (Unique)
- `issue_date`
- `due_date`
- `total_amount`
- `discount_amount`
- `net_amount`
- `status` (Unpaid, Partially Paid, Paid, Overdue, Cancelled)
- `remarks`
- `created_by` (Foreign Key to User) **Many-to-One**

**Relationships:** One-to-Many with InvoiceItem, Payment

### InvoiceItem

- `id` (Primary Key)
- `invoice_id` (Foreign Key to Invoice) **Many-to-One**
- `fee_structure_id` (Foreign Key to FeeStructure) **Many-to-One** (Optional)
- `special_fee_id` (Foreign Key to SpecialFee) **Many-to-One** (Optional)
- `description`
- `amount`
- `discount_amount`
- `net_amount`

### Payment

- `id` (Primary Key)
- `invoice_id` (Foreign Key to Invoice) **Many-to-One**
- `payment_date`
- `amount`
- `payment_method` (Cash, Bank Transfer, Credit Card, Mobile Payment)
- `transaction_id`
- `received_by` (Foreign Key to User) **Many-to-One**
- `receipt_number` (Unique)
- `remarks`
- `status` (Completed, Pending, Failed, Refunded)

### FinancialSummary

- `id` (Primary Key)
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `month`
- `year`
- `total_fees_due`
- `total_fees_collected`
- `total_outstanding`
- `total_scholarships_given`
- `total_expenses`
- `net_income`
- `generated_at` (Timestamp)

## Library Management

### BookCategory

- `id` (Primary Key)
- `name` (Fiction, Science, History, etc.)
- `description`
- `parent_category_id` (Self-reference) **Many-to-One**

**Relationships:** One-to-Many with Book

### Book

- `id` (Primary Key)
- `title`
- `author`
- `isbn` (Unique)
- `publisher`
- `publication_year`
- `edition`
- `category_id` (Foreign Key to BookCategory) **Many-to-One**
- `description`
- `pages`
- `price`
- `shelf_location`
- `cover_image`
- `total_copies`
- `available_copies`

**Relationships:** One-to-Many with BookCopy, BookIssue, BookReservation

### BookCopy

- `id` (Primary Key)
- `book_id` (Foreign Key to Book) **Many-to-One**
- `copy_number`
- `procurement_date`
- `status` (Available, Issued, Reserved, Lost, Damaged)
- `remarks`

### BookIssue

- `id` (Primary Key)
- `book_copy_id` (Foreign Key to BookCopy) **Many-to-One**
- `issued_to_id` (Foreign Key to User) **Many-to-One**
- `issued_by_id` (Foreign Key to User) **Many-to-One**
- `issue_date`
- `due_date`
- `return_date`
- `is_returned` (Boolean)
- `fine_amount`
- `fine_paid` (Boolean)
- `remarks`

## Analytics and Reporting Tables

### StudentPerformanceAnalytics

- `id` (Primary Key)
- `student_id` (Foreign Key to Student) **Many-to-One**
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `subject_id` (Foreign Key to Subject) **Many-to-One**
- `average_marks`
- `highest_marks`
- `lowest_marks`
- `attendance_percentage`
- `assignment_completion_rate`
- `ranking_in_class`
- `ranking_in_grade`
- `improvement_trend` (Improving, Declining, Stable)
- `calculated_at` (Timestamp)

### ClassPerformanceAnalytics

- `id` (Primary Key)
- `class_id` (Foreign Key to Class) **Many-to-One**
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `subject_id` (Foreign Key to Subject) **Many-to-One**
- `class_average`
- `highest_score`
- `lowest_score`
- `pass_rate`
- `total_students`
- `students_above_average`
- `students_below_average`
- `calculated_at` (Timestamp)

### AttendanceAnalytics

- `id` (Primary Key)
- `entity_type` (Student, Class, Grade, Section)
- `entity_id`
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `month`
- `total_days`
- `present_days`
- `absent_days`
- `late_days`
- `attendance_percentage`
- `calculated_at` (Timestamp)

### FinancialAnalytics

- `id` (Primary Key)
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `section_id` (Foreign Key to Section) **Many-to-One** (Optional)
- `grade_id` (Foreign Key to Grade) **Many-to-One** (Optional)
- `fee_category_id` (Foreign Key to FeeCategory) **Many-to-One** (Optional)
- `total_expected_revenue`
- `total_collected_revenue`
- `collection_rate`
- `total_outstanding`
- `number_of_defaulters`
- `calculated_at` (Timestamp)

### TeacherPerformanceAnalytics

- `id` (Primary Key)
- `teacher_id` (Foreign Key to Teacher) **Many-to-One**
- `academic_year_id` (Foreign Key to AcademicYear) **Many-to-One**
- `term_id` (Foreign Key to Term) **Many-to-One**
- `classes_taught`
- `subjects_taught`
- `average_class_performance`
- `student_satisfaction_score`
- `attendance_rate`
- `assignments_given`
- `assignments_graded_on_time`
- `calculated_at` (Timestamp)

## Communication & Notifications

### Announcement

- `id` (Primary Key)
- `title`
- `content`
- `created_by` (Foreign Key to User) **Many-to-One**
- `created_at` (Timestamp)
- `target_audience` (All, Students, Teachers, Parents, Staff)
- `target_grades` (JSON array of grade IDs)
- `target_classes` (JSON array of class IDs)
- `start_date`
- `end_date`
- `is_active` (Boolean)
- `attachment`
- `priority` (High, Medium, Low)

### Notification

- `id` (Primary Key)
- `user_id` (Foreign Key to User) **Many-to-One**
- `title`
- `content`
- `notification_type` (System, Attendance, Fee, Exam, Assignment, etc.)
- `reference_id`
- `reference_type` (Invoice, Assignment, Exam, etc.)
- `created_at` (Timestamp)
- `is_read` (Boolean)
- `read_at` (Timestamp)
- `priority` (High, Medium, Low)

## System Configuration

### SystemSetting

- `id` (Primary Key)
- `setting_key` (Unique)
- `setting_value`
- `data_type` (String, Number, Boolean, JSON)
- `description`
- `is_editable` (Boolean)
- `category` (Academic, Financial, System, etc.)

### AuditLog

- `id` (Primary Key)
- `user_id` (Foreign Key to User) **Many-to-One**
- `action` (Create, Update, Delete, Login, Logout, etc.)
- `entity_type`
- `entity_id`
- `data_before` (JSON)
- `data_after` (JSON)
- `ip_address`
- `user_agent`
- `timestamp`

## Key Relationships Summary

- **User**: Central entity with One-to-One relationships with Student, Teacher, Parent
- **Department**: One-to-Many with Section
- **Section**: One-to-Many with Grade, FeeStructure (e.g., "Lower Primary", "Upper Primary")
- **Grade**: Many-to-One with Section, One-to-Many with Class (e.g., "Grade 3" in "Lower Primary")
- **Class**: Many-to-One with Grade, named descriptively (e.g., "North", "Blue" → "Grade 3 North")
- **AcademicYear**: One-to-Many with Terms, Classes, Exams
- **Term**: Many-to-One with AcademicYear, One-to-Many with FeeStructures, Invoices
- **Student**: Many-to-Many with Parents, One-to-Many with various academic records
- **FeeStructure**: Can be linked to Section and/or Grade for flexible fee assignment
- **SpecialFee**: Can target specific Classes or Students for custom charges
- **Analytics Tables**: Provide aggregated data for reporting and insights at Section, Grade, and Class levels
