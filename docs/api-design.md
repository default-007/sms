# School Management System - API Design

## API Overview

The School Management System API follows a RESTful architecture with resource-based URLs, proper HTTP methods, and status codes. The API is versioned to ensure backward compatibility as the system evolves.

## Base URL

```
https://api.schoolmanagementsystem.com/v1/
```

## Authentication

All API endpoints (except for login and public endpoints) require authentication using JWT (JSON Web Tokens).

- **Login**: POST `/auth/login`
- **Refresh Token**: POST `/auth/refresh`
- **Logout**: POST `/auth/logout`

Authentication headers:
```
Authorization: Bearer {jwt_token}
```

## Common Response Format

```json
{
  "status": "success|error",
  "message": "Description of the result",
  "data": { /* Response data */ },
  "meta": {
    "pagination": {
      "total": 100,
      "per_page": 20,
      "current_page": 1,
      "last_page": 5,
      "next_page_url": "/api/v1/resource?page=2",
      "prev_page_url": null
    }
  }
}
```

## Error Handling

```json
{
  "status": "error",
  "message": "Error description",
  "errors": {
    "field1": ["Error message 1", "Error message 2"],
    "field2": ["Error message"]
  },
  "code": "ERROR_CODE"
}
```

Common HTTP status codes:
- 200: OK
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 422: Unprocessable Entity
- 500: Internal Server Error

## API Endpoints

### User Management

#### Users

- **List Users**: GET `/users`
  - Query parameters: `role`, `status`, `search`, `page`, `per_page`
  
- **Get User**: GET `/users/{id}`

- **Create User**: POST `/users`
  - Body: user details including role assignments

- **Update User**: PUT `/users/{id}`
  - Body: updated user details

- **Delete User**: DELETE `/users/{id}`

- **Change Password**: POST `/users/{id}/change-password`
  - Body: `old_password`, `new_password`, `confirm_password`

#### Roles

- **List Roles**: GET `/roles`

- **Get Role**: GET `/roles/{id}`

- **Create Role**: POST `/roles`
  - Body: role details and permissions

- **Update Role**: PUT `/roles/{id}`
  - Body: updated role details and permissions

- **Delete Role**: DELETE `/roles/{id}`

- **List Role Permissions**: GET `/roles/{id}/permissions`

### Student Management

#### Students

- **List Students**: GET `/students`
  - Query parameters: `class_id`, `status`, `search`, `page`, `per_page`

- **Get Student**: GET `/students/{id}`

- **Create Student**: POST `/students`
  - Body: student details including user information

- **Update Student**: PUT `/students/{id}`
  - Body: updated student details

- **Delete Student**: DELETE `/students/{id}`

- **Get Student Report Card**: GET `/students/{id}/report-cards`
  - Query parameters: `academic_year`, `term`

- **Get Student Attendance**: GET `/students/{id}/attendance`
  - Query parameters: `start_date`, `end_date`, `class_id`

- **Get Student Fees**: GET `/students/{id}/fees`
  - Query parameters: `academic_year`, `status`

#### Attendance

- **List Attendance**: GET `/attendance`
  - Query parameters: `class_id`, `date`, `status`

- **Get Class Attendance**: GET `/classes/{id}/attendance`
  - Query parameters: `date`, `month`, `year`

- **Mark Attendance**: POST `/attendance`
  - Body: `class_id`, `date`, attendance records for multiple students

- **Update Attendance**: PUT `/attendance/{id}`
  - Body: updated attendance details

### Teacher Management

#### Teachers

- **List Teachers**: GET `/teachers`
  - Query parameters: `department_id`, `status`, `search`, `page`, `per_page`

- **Get Teacher**: GET `/teachers/{id}`

- **Create Teacher**: POST `/teachers`
  - Body: teacher details including user information

- **Update Teacher**: PUT `/teachers/{id}`
  - Body: updated teacher details

- **Delete Teacher**: DELETE `/teachers/{id}`

- **Get Teacher Schedule**: GET `/teachers/{id}/schedule`
  - Query parameters: `day`, `academic_year`

- **Get Teacher Classes**: GET `/teachers/{id}/classes`
  - Query parameters: `academic_year`

#### Teacher Evaluations

- **List Evaluations**: GET `/teachers/{id}/evaluations`

- **Create Evaluation**: POST `/teachers/{id}/evaluations`
  - Body: evaluation details

- **Update Evaluation**: PUT `/evaluations/{id}`
  - Body: updated evaluation details

- **Delete Evaluation**: DELETE `/evaluations/{id}`

### Course & Class Management

#### Departments

- **List Departments**: GET `/departments`

- **Get Department**: GET `/departments/{id}`

- **Create Department**: POST `/departments`
  - Body: department details

- **Update Department**: PUT `/departments/{id}`
  - Body: updated department details

- **Delete Department**: DELETE `/departments/{id}`

#### Academic Years

- **List Academic Years**: GET `/academic-years`

- **Get Academic Year**: GET `/academic-years/{id}`

- **Create Academic Year**: POST `/academic-years`
  - Body: academic year details

- **Update Academic Year**: PUT `/academic-years/{id}`
  - Body: updated academic year details

- **Delete Academic Year**: DELETE `/academic-years/{id}`

- **Set Current Academic Year**: POST `/academic-years/{id}/set-current`

#### Grades & Sections

- **List Grades**: GET `/grades`
  - Query parameters: `department_id`

- **Get Grade**: GET `/grades/{id}`

- **Create Grade**: POST `/grades`
  - Body: grade details

- **Update Grade**: PUT `/grades/{id}`
  - Body: updated grade details

- **Delete Grade**: DELETE `/grades/{id}`

- **List Sections**: GET `/sections`

- **Get Section**: GET `/sections/{id}`

- **Create Section**: POST `/sections`
  - Body: section details

- **Update Section**: PUT `/sections/{id}`
  - Body: updated section details

- **Delete Section**: DELETE `/sections/{id}`

#### Classes

- **List Classes**: GET `/classes`
  - Query parameters: `academic_year_id`, `grade_id`, `section_id`

- **Get Class**: GET `/classes/{id}`

- **Create Class**: POST `/classes`
  - Body: class details including grade and section

- **Update Class**: PUT `/classes/{id}`
  - Body: updated class details

- **Delete Class**: DELETE `/classes/{id}`

- **Get Class Students**: GET `/classes/{id}/students`

- **Get Class Timetable**: GET `/classes/{id}/timetable`
  - Query parameters: `day`

#### Subjects

- **List Subjects**: GET `/subjects`
  - Query parameters: `department_id`, `grade_id`

- **Get Subject**: GET `/subjects/{id}`

- **Create Subject**: POST `/subjects`
  - Body: subject details

- **Update Subject**: PUT `/subjects/{id}`
  - Body: updated subject details

- **Delete Subject**: DELETE `/subjects/{id}`

#### Syllabus

- **List Syllabus**: GET `/syllabus`
  - Query parameters: `subject_id`, `grade_id`, `academic_year_id`

- **Get Syllabus**: GET `/syllabus/{id}`

- **Create Syllabus**: POST `/syllabus`
  - Body: syllabus details

- **Update Syllabus**: PUT `/syllabus/{id}`
  - Body: updated syllabus details

- **Delete Syllabus**: DELETE `/syllabus/{id}`

#### Timetable

- **List Timetable Slots**: GET `/timetable`
  - Query parameters: `class_id`, `subject_id`, `teacher_id`, `day`

- **Get Timetable Slot**: GET `/timetable/{id}`

- **Create Timetable Slot**: POST `/timetable`
  - Body: timetable details

- **Update Timetable Slot**: PUT `/timetable/{id}`
  - Body: updated timetable details

- **Delete Timetable Slot**: DELETE `/timetable/{id}`

- **Generate Timetable**: POST `/timetable/generate`
  - Body: parameters for auto-generation

#### Assignments

- **List Assignments**: GET `/assignments`
  - Query parameters: `class_id`, `subject_id`, `teacher_id`, `status`

- **Get Assignment**: GET `/assignments/{id}`

- **Create Assignment**: POST `/assignments`
  - Body: assignment details

- **Update Assignment**: PUT `/assignments/{id}`
  - Body: updated assignment details

- **Delete Assignment**: DELETE `/assignments/{id}`

- **Get Assignment Submissions**: GET `/assignments/{id}/submissions`

- **Submit Assignment**: POST `/assignments/{id}/submit`
  - Body: submission details

- **Grade Assignment Submission**: PUT `/assignment-submissions/{id}/grade`
  - Body: grading details

### Exams & Assessments

#### Exam Types

- **List Exam Types**: GET `/exam-types`

- **Get Exam Type**: GET `/exam-types/{id}`

- **Create Exam Type**: POST `/exam-types`
  - Body: exam type details

- **Update Exam Type**: PUT `/exam-types/{id}`
  - Body: updated exam type details

- **Delete Exam Type**: DELETE `/exam-types/{id}`

#### Exams

- **List Exams**: GET `/exams`
  - Query parameters: `academic_year_id`, `exam_type_id`, `status`

- **Get Exam**: GET `/exams/{id}`

- **Create Exam**: POST `/exams`
  - Body: exam details

- **Update Exam**: PUT `/exams/{id}`
  - Body: updated exam details

- **Delete Exam**: DELETE `/exams/{id}`

- **Get Exam Schedule**: GET `/exams/{id}/schedule`

- **Create Exam Schedule**: POST `/exams/{id}/schedule`
  - Body: schedule details for multiple subjects

#### Exam Results

- **List Exam Results**: GET `/exam-results`
  - Query parameters: `exam_id`, `class_id`, `student_id`

- **Get Student Exam Result**: GET `/students/{id}/exam-results`
  - Query parameters: `exam_id`

- **Enter Exam Results**: POST `/exam-results`
  - Body: results for multiple students

- **Update Exam Result**: PUT `/exam-results/{id}`
  - Body: updated result details

#### Quizzes

- **List Quizzes**: GET `/quizzes`
  - Query parameters: `class_id`, `subject_id`, `teacher_id`, `status`

- **Get Quiz**: GET `/quizzes/{id}`

- **Create Quiz**: POST `/quizzes`
  - Body: quiz details

- **Update Quiz**: PUT `/quizzes/{id}`
  - Body: updated quiz details

- **Delete Quiz**: DELETE `/quizzes/{id}`

- **Get Quiz Questions**: GET `/quizzes/{id}/questions`

- **Add Quiz Question**: POST `/quizzes/{id}/questions`
  - Body: question details

- **Start Quiz Attempt**: POST `/quizzes/{id}/attempts`
  - Body: student ID

- **Submit Quiz Response**: POST `/quiz-attempts/{id}/responses`
  - Body: answer details

- **End Quiz Attempt**: PUT `/quiz-attempts/{id}/end`

#### Grading System

- **List Grading Systems**: GET `/grading-systems`
  - Query parameters: `academic_year_id`

- **Get Grading System**: GET `/grading-systems/{id}`

- **Create Grading System**: POST `/grading-systems`
  - Body: grading system details

- **Update Grading System**: PUT `/grading-systems/{id}`
  - Body: updated grading system details

- **Delete Grading System**: DELETE `/grading-systems/{id}`

#### Report Cards

- **List Report Cards**: GET `/report-cards`
  - Query parameters: `class_id`, `academic_year_id`, `term`

- **Get Report Card**: GET `/report-cards/{id}`

- **Generate Report Cards**: POST `/report-cards/generate`
  - Body: parameters for generation (class, term, etc.)

- **Update Report Card**: PUT `/report-cards/{id}`
  - Body: updated report card details

- **Delete Report Card**: DELETE `/report-cards/{id}`

- **Publish Report Cards**: POST `/report-cards/publish`
  - Body: IDs of report cards to publish

### Fee & Finance Management

#### Fee Categories

- **List Fee Categories**: GET `/fee-categories`

- **Get Fee Category**: GET `/fee-categories/{id}`

- **Create Fee Category**: POST `/fee-categories`
  - Body: fee category details

- **Update Fee Category**: PUT `/fee-categories/{id}`
  - Body: updated fee category details

- **Delete Fee Category**: DELETE `/fee-categories/{id}`

#### Fee Structures

- **List Fee Structures**: GET `/fee-structures`
  - Query parameters: `academic_year_id`, `grade_id`, `fee_category_id`

- **Get Fee Structure**: GET `/fee-structures/{id}`

- **Create Fee Structure**: POST `/fee-structures`
  - Body: fee structure details

- **Update Fee Structure**: PUT `/fee-structures/{id}`
  - Body: updated fee structure details

- **Delete Fee Structure**: DELETE `/fee-structures/{id}`

#### Scholarships

- **List Scholarships**: GET `/scholarships`
  - Query parameters: `academic_year_id`

- **Get Scholarship**: GET `/scholarships/{id}`

- **Create Scholarship**: POST `/scholarships`
  - Body: scholarship details

- **Update Scholarship**: PUT `/scholarships/{id}`
  - Body: updated scholarship details

- **Delete Scholarship**: DELETE `/scholarships/{id}`

- **Assign Scholarship**: POST `/students/{id}/scholarships`
  - Body: scholarship assignment details

- **List Student Scholarships**: GET `/students/{id}/scholarships`

#### Invoices

- **List Invoices**: GET `/invoices`
  - Query parameters: `student_id`, `class_id`, `status`, `date_range`

- **Get Invoice**: GET `/invoices/{id}`

- **Generate Invoices**: POST `/invoices/generate`
  - Body: parameters for generation (class, fee category, etc.)

- **Update Invoice**: PUT `/invoices/{id}`
  - Body: updated invoice details

- **Delete Invoice**: DELETE `/invoices/{id}`

- **Get Invoice Items**: GET `/invoices/{id}/items`

#### Payments

- **List Payments**: GET `/payments`
  - Query parameters: `invoice_id`, `student_id`, `payment_method`, `date_range`

- **Get Payment**: GET `/payments/{id}`

- **Record Payment**: POST `/payments`
  - Body: payment details

- **Update Payment**: PUT `/payments/{id}`
  - Body: updated payment details

- **Delete Payment**: DELETE `/payments/{id}`

- **Generate Receipt**: GET `/payments/{id}/receipt`

#### Expenses

- **List Expenses**: GET `/expenses`
  - Query parameters: `category`, `date_range`

- **Get Expense**: GET `/expenses/{id}`

- **Create Expense**: POST `/expenses`
  - Body: expense details

- **Update Expense**: PUT `/expenses/{id}`
  - Body: updated expense details

- **Delete Expense**: DELETE `/expenses/{id}`

### Library Management

#### Book Categories

- **List Book Categories**: GET `/book-categories`

- **Get Book Category**: GET `/book-categories/{id}`

- **Create Book Category**: POST `/book-categories`
  - Body: category details

- **Update Book Category**: PUT `/book-categories/{id}`
  - Body: updated category details

- **Delete Book Category**: DELETE `/book-categories/{id}`

#### Books

- **List Books**: GET `/books`
  - Query parameters: `category_id`, `status`, `search`

- **Get Book**: GET `/books/{id}`

- **Create Book**: POST `/books`
  - Body: book details

- **Update Book**: PUT `/books/{id}`
  - Body: updated book details

- **Delete Book**: DELETE `/books/{id}`

- **Get Book Copies**: GET `/books/{id}/copies`

- **Add Book Copy**: POST `/books/{id}/copies`
  - Body: copy details

#### Book Issues

- **List Book Issues**: GET `/book-issues`
  - Query parameters: `user_id`, `status`, `date_range`

- **Get Book Issue**: GET `/book-issues/{id}`

- **Issue Book**: POST `/book-issues`
  - Body: issue details

- **Return Book**: PUT `/book-issues/{id}/return`
  - Body: return details including fine if applicable

- **Get User's Issued Books**: GET `/users/{id}/book-issues`

#### Book Reservations

- **List Reservations**: GET `/book-reservations`
  - Query parameters: `book_id`, `user_id`, `status`

- **Get Reservation**: GET `/book-reservations/{id}`

- **Create Reservation**: POST `/book-reservations`
  - Body: reservation details

- **Update Reservation**: PUT `/book-reservations/{id}`
  - Body: updated reservation details

- **Cancel Reservation**: DELETE `/book-reservations/{id}`

### Transport Management

#### Vehicles

- **List Vehicles**: GET `/vehicles`
  - Query parameters: `status`, `type`

- **Get Vehicle**: GET `/vehicles/{id}`

- **Create Vehicle**: POST `/vehicles`
  - Body: vehicle details

- **Update Vehicle**: PUT `/vehicles/{id}`
  - Body: updated vehicle details

- **Delete Vehicle**: DELETE `/vehicles/{id}`

#### Drivers

- **List Drivers**: GET `/drivers`
  - Query parameters: `status`

- **Get Driver**: GET `/drivers/{id}`

- **Create Driver**: POST `/drivers`
  - Body: driver details

- **Update Driver**: PUT `/drivers/{id}`
  - Body: updated driver details

- **Delete Driver**: DELETE `/drivers/{id}`

#### Routes

- **List Routes**: GET `/routes`
  - Query parameters: `status`

- **Get Route**: GET `/routes/{id}`

- **Create Route**: POST `/routes`
  - Body: route details

- **Update Route**: PUT `/routes/{id}`
  - Body: updated route details

- **Delete Route**: DELETE `/routes/{id}`

- **Get Route Stops**: GET `/routes/{id}/stops`

- **Add Route Stop**: POST `/routes/{id}/stops`
  - Body: stop details

#### Transport Assignments

- **List Transport Assignments**: GET `/transport-assignments`
  - Query parameters: `route_id`, `vehicle_id`, `driver_id`

- **Get Transport Assignment**: GET `/transport-assignments/{id}`

- **Create Transport Assignment**: POST `/transport-assignments`
  - Body: assignment details

- **Update Transport Assignment**: PUT `/transport-assignments/{id}`
  - Body: updated assignment details

- **Delete Transport Assignment**: DELETE `/transport-assignments/{id}`

#### Student Transport

- **List Student Transport**: GET `/student-transport`
  - Query parameters: `student_id`, `route_id`, `status`

- **Get Student Transport**: GET `/student-transport/{id}`

- **Assign Student Transport**: POST `/student-transport`
  - Body: transport assignment details

- **Update Student Transport**: PUT `/student-transport/{id}`
  - Body: updated transport details

- **Delete Student Transport**: DELETE `/student-transport/{id}`

### Communication & Notifications

#### Announcements

- **List Announcements**: GET `/announcements`
  - Query parameters: `target_audience`, `is_active`, `date_range`

- **Get Announcement**: GET `/announcements/{id}`

- **Create Announcement**: POST `/announcements`
  - Body: announcement details

- **Update Announcement**: PUT `/announcements/{id}`
  - Body: updated announcement details

- **Delete Announcement**: DELETE `/announcements/{id}`

#### Messages

- **List Messages**: GET `/messages`
  - Query parameters: `sender_id`, `receiver_id`, `is_read`

- **Get Message**: GET `/messages/{id}`

- **Send Message**: POST `/messages`
  - Body: message details

- **Mark Message as Read**: PUT `/messages/{id}/read`

- **Delete Message**: DELETE `/messages/{id}`

#### Notifications

- **List Notifications**: GET `/notifications`
  - Query parameters: `is_read`, `type`

- **Get Notification**: GET `/notifications/{id}`

- **Mark Notification as Read**: PUT `/notifications/{id}/read`

- **Delete Notification**: DELETE `/notifications/{id}`

- **Send Notification**: POST `/notifications/send`
  - Body: notification details including recipients

### Reports & Analytics

- **Student Attendance Report**: GET `/reports/student-attendance`
  - Query parameters: `class_id`, `date_range`, `student_id`

- **Class Attendance Report**: GET `/reports/class-attendance`
  - Query parameters: `class_id`, `date_range`

- **Fee Collection Report**: GET `/reports/fee-collection`
  - Query parameters: `date_range`, `class_id`, `fee_category_id`

- **Exam Results Report**: GET `/reports/exam-results`
  - Query parameters: `exam_id`, `class_id`, `subject_id`

- **Student Performance Report**: GET `/reports/student-performance`
  - Query parameters: `student_id`, `academic_year_id`

- **Teacher Performance Report**: GET `/reports/teacher-performance`
  - Query parameters: `teacher_id`, `academic_year_id`

- **Library Usage Report**: GET `/reports/library-usage`
  - Query parameters: `date_range`, `user_type`

- **Transport Utilization Report**: GET `/reports/transport-utilization`
  - Query parameters: `route_id`, `academic_year_id`

- **Financial Report**: GET `/reports/financial`
  - Query parameters: `report_type`, `date_range`

## Webhooks

The API supports webhooks for real-time notifications about various events:

- **Register Webhook**: POST `/webhooks`
  - Body: webhook URL and events to subscribe to

- **List Webhooks**: GET `/webhooks`

- **Delete Webhook**: DELETE `/webhooks/{id}`

## API Rate Limiting

The API implements rate limiting to prevent abuse:

- Standard rate limit: 60 requests per minute
- Admin rate limit: 120 requests per minute

Rate limit headers are included in the response:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 58
X-RateLimit-Reset: 1623456789
```

## API Documentation

Interactive API documentation is available at:
```
https://api.schoolmanagementsystem.com/docs
```

The documentation is built using OpenAPI 3.0 and includes comprehensive descriptions, request/response examples, and a sandbox to test the API endpoints.
