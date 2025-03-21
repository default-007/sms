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

### UserRole
- `id` (Primary Key)
- `name` (e.g., Admin, Teacher, Parent, Staff)
- `description`
- `permissions` (JSON field storing permission details)

### UserRoleAssignment
- `id` (Primary Key)
- `user_id` (Foreign Key to User)
- `role_id` (Foreign Key to UserRole)
- `assigned_date`
- `assigned_by` (Foreign Key to User)

## Student Management

### Student
- `id` (Primary Key)
- `user_id` (Foreign Key to User)
- `admission_number` (Unique)
- `admission_date`
- `current_class_id` (Foreign Key to Class)
- `roll_number`
- `blood_group`
- `medical_conditions`
- `emergency_contact_name`
- `emergency_contact_number`
- `previous_school`
- `status` (Active, Inactive, Graduated, etc.)

### Parent
- `id` (Primary Key)
- `user_id` (Foreign Key to User)
- `occupation`
- `annual_income`
- `education`
- `relation_with_student` (Father, Mother, Guardian)

### StudentParentRelation
- `id` (Primary Key)
- `student_id` (Foreign Key to Student)
- `parent_id` (Foreign Key to Parent)
- `is_primary_contact` (Boolean)

### Attendance
- `id` (Primary Key)
- `student_id` (Foreign Key to Student)
- `class_id` (Foreign Key to Class)
- `date`
- `status` (Present, Absent, Late, Excused)
- `remarks`
- `marked_by` (Foreign Key to User)
- `marked_at` (Timestamp)

## Teacher Management

### Teacher
- `id` (Primary Key)
- `user_id` (Foreign Key to User)
- `employee_id` (Unique)
- `joining_date`
- `qualification`
- `experience_years`
- `specialization`
- `department_id` (Foreign Key to Department)
- `position`
- `salary`
- `contract_type` (Permanent, Temporary, Contract)
- `status` (Active, On Leave, Terminated)

### TeacherClassAssignment
- `id` (Primary Key)
- `teacher_id` (Foreign Key to Teacher)
- `class_id` (Foreign Key to Class)
- `subject_id` (Foreign Key to Subject)
- `academic_year_id` (Foreign Key to AcademicYear)
- `is_class_teacher` (Boolean)

### TeacherEvaluation
- `id` (Primary Key)
- `teacher_id` (Foreign Key to Teacher)
- `evaluator_id` (Foreign Key to User)
- `evaluation_date`
- `criteria` (JSON field for evaluation parameters)
- `score`
- `remarks`
- `followup_actions`

## Course & Class Management

### Department
- `id` (Primary Key)
- `name`
- `description`
- `head_id` (Foreign Key to Teacher)
- `creation_date`

### AcademicYear
- `id` (Primary Key)
- `name` (e.g., "2023-2024")
- `start_date`
- `end_date`
- `is_current` (Boolean)

### Grade
- `id` (Primary Key)
- `name` (e.g., "Grade 1", "Grade 2")
- `description`
- `department_id` (Foreign Key to Department)

### Section
- `id` (Primary Key)
- `name` (e.g., "A", "B", "C")
- `description`

### Class
- `id` (Primary Key)
- `grade_id` (Foreign Key to Grade)
- `section_id` (Foreign Key to Section)
- `academic_year_id` (Foreign Key to AcademicYear)
- `room_number`
- `capacity`
- `class_teacher_id` (Foreign Key to Teacher)

### Subject
- `id` (Primary Key)
- `name`
- `code` (Unique)
- `description`
- `department_id` (Foreign Key to Department)
- `credit_hours`
- `is_elective` (Boolean)

### Syllabus
- `id` (Primary Key)
- `subject_id` (Foreign Key to Subject)
- `grade_id` (Foreign Key to Grade)
- `academic_year_id` (Foreign Key to AcademicYear)
- `title`
- `description`
- `content` (JSON or Text field storing syllabus structure)
- `created_by` (Foreign Key to User)
- `last_updated_by` (Foreign Key to User)
- `last_updated_at` (Timestamp)

### TimeSlot
- `id` (Primary Key)
- `day_of_week`
- `start_time`
- `end_time`
- `duration_minutes`

### Timetable
- `id` (Primary Key)
- `class_id` (Foreign Key to Class)
- `subject_id` (Foreign Key to Subject)
- `teacher_id` (Foreign Key to Teacher)
- `time_slot_id` (Foreign Key to TimeSlot)
- `room`
- `effective_from_date`
- `effective_to_date`
- `is_active` (Boolean)

### Assignment
- `id` (Primary Key)
- `title`
- `description`
- `class_id` (Foreign Key to Class)
- `subject_id` (Foreign Key to Subject)
- `teacher_id` (Foreign Key to Teacher)
- `assigned_date`
- `due_date`
- `total_marks`
- `attachment` (File path or URL)
- `submission_type` (Online, Physical)
- `status` (Draft, Published, Closed)

### AssignmentSubmission
- `id` (Primary Key)
- `assignment_id` (Foreign Key to Assignment)
- `student_id` (Foreign Key to Student)
- `submission_date`
- `content` (Text or File path)
- `remarks`
- `marks_obtained`
- `status` (Submitted, Late, Graded)
- `graded_by` (Foreign Key to Teacher)
- `graded_at` (Timestamp)

## Exams & Assessments

### ExamType
- `id` (Primary Key)
- `name` (e.g., Mid-term, Final, Quiz)
- `description`
- `contribution_percentage` (How much it contributes to final grade)

### Exam
- `id` (Primary Key)
- `name`
- `exam_type_id` (Foreign Key to ExamType)
- `academic_year_id` (Foreign Key to AcademicYear)
- `start_date`
- `end_date`
- `description`
- `created_by` (Foreign Key to User)
- `status` (Scheduled, Ongoing, Completed, Cancelled)

### ExamSchedule
- `id` (Primary Key)
- `exam_id` (Foreign Key to Exam)
- `class_id` (Foreign Key to Class)
- `subject_id` (Foreign Key to Subject)
- `date`
- `start_time`
- `end_time`
- `room`
- `supervisor_id` (Foreign Key to Teacher)
- `total_marks`
- `passing_marks`

### Quiz
- `id` (Primary Key)
- `title`
- `description`
- `class_id` (Foreign Key to Class)
- `subject_id` (Foreign Key to Subject)
- `teacher_id` (Foreign Key to Teacher)
- `start_datetime`
- `end_datetime`
- `duration_minutes`
- `total_marks`
- `passing_marks`
- `attempts_allowed`
- `status` (Draft, Published, Closed)

### Question
- `id` (Primary Key)
- `quiz_id` (Foreign Key to Quiz)
- `question_text`
- `question_type` (MCQ, True/False, Short Answer, etc.)
- `options` (JSON field for MCQ options)
- `correct_answer`
- `marks`
- `difficulty_level` (Easy, Medium, Hard)

### StudentExamResult
- `id` (Primary Key)
- `student_id` (Foreign Key to Student)
- `exam_schedule_id` (Foreign Key to ExamSchedule)
- `marks_obtained`
- `percentage`
- `grade`
- `remarks`
- `is_pass` (Boolean)
- `entered_by` (Foreign Key to User)
- `entry_date` (Timestamp)

### StudentQuizAttempt
- `id` (Primary Key)
- `student_id` (Foreign Key to Student)
- `quiz_id` (Foreign Key to Quiz)
- `start_time`
- `end_time`
- `marks_obtained`
- `percentage`
- `is_pass` (Boolean)
- `attempt_number`

### StudentQuizResponse
- `id` (Primary Key)
- `student_quiz_attempt_id` (Foreign Key to StudentQuizAttempt)
- `question_id` (Foreign Key to Question)
- `selected_option` (For MCQ)
- `answer_text` (For short answer questions)
- `is_correct` (Boolean)
- `marks_obtained`

### GradingSystem
- `id` (Primary Key)
- `academic_year_id` (Foreign Key to AcademicYear)
- `grade_name` (e.g., A, B, C)
- `min_percentage`
- `max_percentage`
- `grade_point`
- `description`

### ReportCard
- `id` (Primary Key)
- `student_id` (Foreign Key to Student)
- `class_id` (Foreign Key to Class)
- `academic_year_id` (Foreign Key to AcademicYear)
- `term` (First, Second, Final)
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
- `name` (e.g., Tuition, Transport, Library)
- `description`
- `is_recurring` (Boolean)
- `frequency` (Monthly, Quarterly, Annually)

### FeeStructure
- `id` (Primary Key)
- `academic_year_id` (Foreign Key to AcademicYear)
- `grade_id` (Foreign Key to Grade)
- `fee_category_id` (Foreign Key to FeeCategory)
- `amount`
- `due_day_of_month` (For recurring fees)
- `late_fee_percentage`
- `grace_period_days`

### Scholarship
- `id` (Primary Key)
- `name`
- `description`
- `discount_type` (Percentage, Fixed Amount)
- `discount_value`
- `criteria` (Merit, Need-based, etc.)
- `academic_year_id` (Foreign Key to AcademicYear)

### StudentScholarship
- `id` (Primary Key)
- `student_id` (Foreign Key to Student)
- `scholarship_id` (Foreign Key to Scholarship)
- `approved_by` (Foreign Key to User)
- `approval_date`
- `start_date`
- `end_date`
- `remarks`
- `status` (Approved, Suspended, Terminated)

### Invoice
- `id` (Primary Key)
- `student_id` (Foreign Key to Student)
- `academic_year_id` (Foreign Key to AcademicYear)
- `invoice_number` (Unique)
- `issue_date`
- `due_date`
- `total_amount`
- `discount_amount`
- `net_amount`
- `status` (Unpaid, Partially Paid, Paid, Overdue, Cancelled)
- `remarks`
- `created_by` (Foreign Key to User)

### InvoiceItem
- `id` (Primary Key)
- `invoice_id` (Foreign Key to Invoice)
- `fee_structure_id` (Foreign Key to FeeStructure)
- `description`
- `amount`
- `discount_amount`
- `net_amount`

### Payment
- `id` (Primary Key)
- `invoice_id` (Foreign Key to Invoice)
- `payment_date`
- `amount`
- `payment_method` (Cash, Bank Transfer, Credit Card)
- `transaction_id`
- `received_by` (Foreign Key to User)
- `receipt_number` (Unique)
- `remarks`
- `status` (Completed, Pending, Failed)

### Expense
- `id` (Primary Key)
- `expense_category` (Salary, Maintenance, Utilities, etc.)
- `amount`
- `expense_date`
- `description`
- `payment_method`
- `paid_to`
- `approved_by` (Foreign Key to User)
- `receipt_attachment` (File path)
- `remarks`

## Library Management

### Book
- `id` (Primary Key)
- `title`
- `author`
- `isbn` (Unique)
- `publisher`
- `publication_year`
- `edition`
- `category_id` (Foreign Key to BookCategory)
- `description`
- `pages`
- `price`
- `shelf_location`
- `cover_image` (File path)
- `status` (Available, Issued, Reserved, Lost, Damaged)

### BookCategory
- `id` (Primary Key)
- `name` (Fiction, Science, History, etc.)
- `description`
- `parent_category_id` (Self-reference for hierarchical categories)

### BookCopy
- `id` (Primary Key)
- `book_id` (Foreign Key to Book)
- `copy_number`
- `procurement_date`
- `status` (Available, Issued, Reserved, Lost, Damaged)
- `remarks`

### BookIssue
- `id` (Primary Key)
- `book_copy_id` (Foreign Key to BookCopy)
- `issued_to_id` (Foreign Key to User)
- `issued_by_id` (Foreign Key to User)
- `issue_date`
- `due_date`
- `return_date`
- `is_returned` (Boolean)
- `fine_amount`
- `fine_paid` (Boolean)
- `remarks`

### LibraryFine
- `id` (Primary Key)
- `book_issue_id` (Foreign Key to BookIssue)
- `amount`
- `days_overdue`
- `payment_status` (Pending, Paid, Waived)
- `payment_date`
- `remarks`

### BookReservation
- `id` (Primary Key)
- `book_id` (Foreign Key to Book)
- `user_id` (Foreign Key to User)
- `reservation_date`
- `expiry_date`
- `status` (Pending, Fulfilled, Expired, Cancelled)
- `remarks`

## Transport Management

### Vehicle
- `id` (Primary Key)
- `registration_number` (Unique)
- `type` (Bus, Van, etc.)
- `model`
- `make`
- `year`
- `seating_capacity`
- `fuel_type`
- `insurance_expiry_date`
- `service_date`
- `status` (Operational, Maintenance, Out of Service)

### Driver
- `id` (Primary Key)
- `user_id` (Foreign Key to User)
- `employee_id` (Unique)
- `license_number`
- `license_expiry_date`
- `joining_date`
- `experience_years`
- `status` (Active, On Leave, Terminated)

### Route
- `id` (Primary Key)
- `name`
- `description`
- `start_point`
- `end_point`
- `distance_km`
- `estimated_time_minutes`
- `fare`
- `status` (Active, Inactive)

### RouteStop
- `id` (Primary Key)
- `route_id` (Foreign Key to Route)
- `stop_name`
- `stop_order` (Sequence number)
- `arrival_time`
- `departure_time`
- `coordinates` (Latitude/Longitude)

### TransportAssignment
- `id` (Primary Key)
- `vehicle_id` (Foreign Key to Vehicle)
- `driver_id` (Foreign Key to Driver)
- `route_id` (Foreign Key to Route)
- `academic_year_id` (Foreign Key to AcademicYear)
- `assignment_date`
- `status` (Active, Inactive)

### StudentTransport
- `id` (Primary Key)
- `student_id` (Foreign Key to Student)
- `route_id` (Foreign Key to Route)
- `route_stop_id` (Foreign Key to RouteStop)
- `academic_year_id` (Foreign Key to AcademicYear)
- `pickup_time`
- `drop_time`
- `start_date`
- `end_date`
- `status` (Active, Inactive)

## Communication & Notifications

### Announcement
- `id` (Primary Key)
- `title`
- `content`
- `created_by` (Foreign Key to User)
- `created_at` (Timestamp)
- `target_audience` (All, Students, Teachers, Parents, Staff)
- `target_classes` (JSON array of class IDs)
- `start_date`
- `end_date`
- `is_active` (Boolean)
- `attachment` (File path)

### Message
- `id` (Primary Key)
- `sender_id` (Foreign Key to User)
- `receiver_id` (Foreign Key to User)
- `subject`
- `content`
- `sent_at` (Timestamp)
- `read_at` (Timestamp)
- `is_read` (Boolean)
- `attachment` (File path)
- `parent_message_id` (Self-reference for threaded conversations)

### Notification
- `id` (Primary Key)
- `user_id` (Foreign Key to User)
- `title`
- `content`
- `notification_type` (System, Attendance, Fee, Exam, etc.)
- `reference_id` (ID of the related entity)
- `created_at` (Timestamp)
- `is_read` (Boolean)
- `read_at` (Timestamp)
- `priority` (High, Medium, Low)

### SMSLog
- `id` (Primary Key)
- `recipient_number`
- `recipient_user_id` (Foreign Key to User)
- `content`
- `sent_at` (Timestamp)
- `status` (Sent, Failed, Pending)
- `error_message`
- `sender` (Service Provider Information)
- `message_id` (From service provider)

### EmailLog
- `id` (Primary Key)
- `recipient_email`
- `recipient_user_id` (Foreign Key to User)
- `subject`
- `content`
- `sent_at` (Timestamp)
- `status` (Sent, Failed, Pending)
- `error_message`
- `attachment` (File path)

## Miscellaneous

### Event
- `id` (Primary Key)
- `title`
- `description`
- `start_datetime`
- `end_datetime`
- `location`
- `event_type` (Academic, Cultural, Sports, etc.)
- `organizer_id` (Foreign Key to User)
- `target_audience` (All, Students, Teachers, Parents)
- `status` (Scheduled, Ongoing, Completed, Cancelled)
- `attachment` (File path)

### Document
- `id` (Primary Key)
- `title`
- `description`
- `file_path`
- `file_type`
- `upload_date`
- `uploaded_by` (Foreign Key to User)
- `category` (Certificate, ID Card, Notice, etc.)
- `related_to_id` (User ID or entity ID)
- `related_to_type` (User, Student, Teacher, etc.)
- `is_public` (Boolean)

### SystemSetting
- `id` (Primary Key)
- `setting_key` (Unique)
- `setting_value`
- `data_type` (String, Number, Boolean, JSON)
- `description`
- `is_editable` (Boolean)

### AuditLog
- `id` (Primary Key)
- `user_id` (Foreign Key to User)
- `action` (Create, Update, Delete, Login, Logout, etc.)
- `entity_type` (User, Student, Teacher, etc.)
- `entity_id`
- `data_before` (JSON representation of data before change)
- `data_after` (JSON representation of data after change)
- `ip_address`
- `user_agent`
- `timestamp`
