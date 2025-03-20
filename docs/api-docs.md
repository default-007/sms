# API Documentation

## Overview
This document provides detailed information about the School Management System API endpoints, authentication, and usage.

## Base URL
- Development: `http://localhost:8000/api/v1`
- Production: `https://api.example.com/v1`

## Authentication
The API uses JWT (JSON Web Tokens) for authentication. Include the token in the Authorization header:

```http
Authorization: Bearer <your_token>
```

### Authentication Endpoints

#### Login
```http
POST /auth/login
Content-Type: application/json

{
    "username": "string",
    "password": "string"
}
```

Response:
```json
{
    "access_token": "string",
    "refresh_token": "string",
    "token_type": "bearer"
}
```

#### Refresh Token
```http
POST /auth/refresh
Authorization: Bearer <refresh_token>
```

## API Endpoints

### User Management

#### Get Users
```http
GET /users
Query Parameters:
- role (string, optional): Filter by user role
- page (integer, optional): Page number
- limit (integer, optional): Items per page
```

#### Create User
```http
POST /users
Content-Type: application/json

{
    "username": "string",
    "email": "string",
    "password": "string",
    "role": "string"
}
```

### Student Management

#### Get Students
```http
GET /students
Query Parameters:
- class (string, optional): Filter by class
- section (string, optional): Filter by section
```

#### Create Student
```http
POST /students
Content-Type: application/json

{
    "first_name": "string",
    "last_name": "string",
    "class": "string",
    "section": "string",
    "admission_date": "date"
}
```

## Error Handling

### Error Codes
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 422: Validation Error
- 500: Internal Server Error

### Error Response Format
```json
{
    "error": {
        "code": "string",
        "message": "string",
        "details": {}
    }
}
```

## Rate Limiting
- Rate limit: 100 requests per minute
- Rate limit header: X-RateLimit-Limit
- Remaining requests header: X-RateLimit-Remaining

## Data Models

### User Model
```json
{
    "id": "uuid",
    "username": "string",
    "email": "string",
    "role": "string",
    "is_active": "boolean",
    "created_at": "datetime"
}
```

### Student Model
```json
{
    "id": "uuid",
    "user_id": "uuid",
    "student_id": "string",
    "class": "string",
    "section": "string",
    "admission_date": "date"
}
```

## Webhook Integration
The system supports webhooks for real-time updates. Configure webhook endpoints in the admin panel.

### Available Events
- student.created
- student.updated
- attendance.marked
- grade.updated

## API Versioning
API versioning is handled through the URL path. Current version: v1

## Best Practices
1. Always check response status codes
2. Implement proper error handling
3. Use pagination for large data sets
4. Cache responses when appropriate
5. Include proper content-type headers