# Database Schema Documentation

## Overview
This document provides a detailed description of the database schema for the School Management System.

## Database Design Principles
- Normalization to 3NF
- Appropriate use of indexes
- Referential integrity
- Data type optimization
- Audit trail implementation

## Schema Definitions

### 1. User Management

#### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
```

#### user_profiles
```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(10),
    contact_number VARCHAR(20),
    address TEXT,
    profile_picture VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
```

### 2. Student Management

#### students
```sql
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    student_id VARCHAR(20) UNIQUE NOT NULL,
    enrollment_date DATE NOT NULL,
    current_class VARCHAR(20) NOT NULL,
    section VARCHAR(10) NOT NULL,
    roll_number INTEGER,
    parent_id UUID REFERENCES users(id),
    academic_year VARCHAR(9) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_students_student_id ON students(student_id);
CREATE INDEX idx_students_class_section ON students(current_class, section);
```

### 3. Academic Management

#### courses
```sql
CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    credits INTEGER NOT NULL,
    class_level VARCHAR(20) NOT NULL,
    academic_year VARCHAR(9) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_courses_code ON courses(course_code);
```

#### classes
```sql
CREATE TABLE classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_name VARCHAR(50) NOT NULL,
    section VARCHAR(10) NOT NULL,
    academic_year VARCHAR(9) NOT NULL,
    class_teacher_id UUID REFERENCES users(id),
    room_number VARCHAR(20),
    capacity INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_name, section, academic_year)
);

CREATE INDEX idx_classes_teacher ON classes(class_teacher_id);
```

### 4. Attendance Management

#### attendance
```sql
CREATE TABLE attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id),
    class_id UUID REFERENCES classes(id),
    date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    remarks TEXT,
    marked_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attendance_student ON attendance(student_id);
CREATE INDEX idx_attendance_date ON attendance(date);
```

### 5. Examination Management

#### exams
```sql
CREATE TABLE exams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    exam_type VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    academic_year VARCHAR(9) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_exams_academic_year ON exams(academic_year);
```

#### exam_results
```sql
CREATE TABLE exam_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id UUID REFERENCES exams(id),
    student_id UUID REFERENCES students(id),
    course_id UUID REFERENCES courses(id),
    marks_obtained DECIMAL(5,2) NOT NULL,
    total_marks DECIMAL(5,2) NOT NULL,
    grade VARCHAR(2),
    remarks TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_exam_results_student ON exam_results(student_id);
CREATE INDEX idx_exam_results_exam ON exam_results(exam_id);
```

## Data Migration Strategy

### 1. Migration Tools
- Alembic for schema migrations
- Custom scripts for data migration
- Validation procedures

### 2. Migration Procedures
- Schema validation
- Data validation
- Rollback procedures
- Version control

## Backup Strategy

### 1. Backup Types
- Full database dumps
- Incremental backups
- Point-in-time recovery
- Transaction logs

### 2. Backup Schedule
- Daily full backups
- Hourly incremental backups
- Real-time transaction logs
- Retention policy

## Performance Optimization

### 1. Indexing Strategy
- Primary key indexes
- Foreign key indexes
- Composite indexes
- Partial indexes

### 2. Query Optimization
- Query planning
- Index usage
- Join optimization
- Materialized views

## Security Measures

### 1. Access Control
- Role-based access
- Row-level security
- Column-level encryption
- Audit logging

### 2. Data Protection
- Encryption at rest
- Secure connections
- Password hashing
- Data masking