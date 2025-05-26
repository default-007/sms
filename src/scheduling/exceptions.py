"""
Custom exceptions for the scheduling module
"""

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.views import exception_handler
from rest_framework.response import Response


class SchedulingException(Exception):
    """Base exception for scheduling module"""

    def __init__(self, message, code=None, details=None):
        self.message = message
        self.code = code or "scheduling_error"
        self.details = details or {}
        super().__init__(self.message)


class TimetableConflictError(SchedulingException):
    """Raised when a timetable conflict is detected"""

    def __init__(self, conflicts, message=None):
        self.conflicts = conflicts
        message = (
            message or f"Timetable conflict detected: {len(conflicts)} conflicts found"
        )
        super().__init__(message, "timetable_conflict", {"conflicts": conflicts})


class TeacherConflictError(TimetableConflictError):
    """Raised when a teacher has conflicting assignments"""

    def __init__(self, teacher, time_slot, conflicting_assignments, message=None):
        self.teacher = teacher
        self.time_slot = time_slot
        self.conflicting_assignments = conflicting_assignments

        conflicts = [
            {
                "type": "teacher",
                "teacher": str(teacher),
                "time_slot": str(time_slot),
                "conflicting_assignments": [
                    str(assignment) for assignment in conflicting_assignments
                ],
            }
        ]

        message = (
            message or f"Teacher {teacher} has conflicting assignments at {time_slot}"
        )
        super().__init__(conflicts, message)


class RoomConflictError(TimetableConflictError):
    """Raised when a room has conflicting bookings"""

    def __init__(self, room, time_slot, conflicting_bookings, message=None):
        self.room = room
        self.time_slot = time_slot
        self.conflicting_bookings = conflicting_bookings

        conflicts = [
            {
                "type": "room",
                "room": str(room),
                "time_slot": str(time_slot),
                "conflicting_bookings": [
                    str(booking) for booking in conflicting_bookings
                ],
            }
        ]

        message = message or f"Room {room} has conflicting bookings at {time_slot}"
        super().__init__(conflicts, message)


class ClassConflictError(TimetableConflictError):
    """Raised when a class has conflicting subjects"""

    def __init__(self, class_obj, time_slot, conflicting_subjects, message=None):
        self.class_obj = class_obj
        self.time_slot = time_slot
        self.conflicting_subjects = conflicting_subjects

        conflicts = [
            {
                "type": "class",
                "class": str(class_obj),
                "time_slot": str(time_slot),
                "conflicting_subjects": [
                    str(subject) for subject in conflicting_subjects
                ],
            }
        ]

        message = (
            message or f"Class {class_obj} has conflicting subjects at {time_slot}"
        )
        super().__init__(conflicts, message)


class OptimizationError(SchedulingException):
    """Raised when timetable optimization fails"""

    def __init__(self, reason, failed_assignments=None, message=None):
        self.reason = reason
        self.failed_assignments = failed_assignments or []

        message = message or f"Timetable optimization failed: {reason}"
        details = {
            "reason": reason,
            "failed_assignments_count": len(self.failed_assignments),
            "failed_assignments": [
                str(assignment) for assignment in self.failed_assignments
            ],
        }

        super().__init__(message, "optimization_failed", details)


class InsufficientResourcesError(OptimizationError):
    """Raised when there are insufficient resources for optimization"""

    def __init__(self, resource_type, required, available, message=None):
        self.resource_type = resource_type
        self.required = required
        self.available = available

        message = (
            message
            or f"Insufficient {resource_type}: required {required}, available {available}"
        )
        super().__init__(f"insufficient_{resource_type}", message=message)


class InvalidTimeSlotError(SchedulingException):
    """Raised when a time slot is invalid"""

    def __init__(self, time_slot, reason, message=None):
        self.time_slot = time_slot
        self.reason = reason

        message = message or f"Invalid time slot {time_slot}: {reason}"
        super().__init__(
            message,
            "invalid_time_slot",
            {"time_slot": str(time_slot), "reason": reason},
        )


class TeacherUnavailableError(SchedulingException):
    """Raised when a teacher is unavailable for assignment"""

    def __init__(self, teacher, time_slot, reason, message=None):
        self.teacher = teacher
        self.time_slot = time_slot
        self.reason = reason

        message = message or f"Teacher {teacher} unavailable at {time_slot}: {reason}"
        super().__init__(
            message,
            "teacher_unavailable",
            {"teacher": str(teacher), "time_slot": str(time_slot), "reason": reason},
        )


class RoomUnavailableError(SchedulingException):
    """Raised when a room is unavailable for booking"""

    def __init__(self, room, time_slot, reason, message=None):
        self.room = room
        self.time_slot = time_slot
        self.reason = reason

        message = message or f"Room {room} unavailable at {time_slot}: {reason}"
        super().__init__(
            message,
            "room_unavailable",
            {"room": str(room), "time_slot": str(time_slot), "reason": reason},
        )


class InvalidSubjectAssignmentError(SchedulingException):
    """Raised when a subject assignment is invalid"""

    def __init__(self, teacher, subject, class_obj, reason, message=None):
        self.teacher = teacher
        self.subject = subject
        self.class_obj = class_obj
        self.reason = reason

        message = (
            message
            or f"Invalid assignment: {teacher} cannot teach {subject} to {class_obj}: {reason}"
        )
        super().__init__(
            message,
            "invalid_subject_assignment",
            {
                "teacher": str(teacher),
                "subject": str(subject),
                "class": str(class_obj),
                "reason": reason,
            },
        )


class TimetableGenerationInProgressError(SchedulingException):
    """Raised when trying to start generation while another is in progress"""

    def __init__(self, term, current_generation, message=None):
        self.term = term
        self.current_generation = current_generation

        message = message or f"Timetable generation already in progress for {term}"
        super().__init__(
            message,
            "generation_in_progress",
            {
                "term": str(term),
                "current_generation_id": str(current_generation.id),
                "started_at": current_generation.started_at.isoformat(),
            },
        )


class ConstraintViolationError(SchedulingException):
    """Raised when a scheduling constraint is violated"""

    def __init__(self, constraint, violation_details, message=None):
        self.constraint = constraint
        self.violation_details = violation_details

        message = message or f"Constraint violation: {constraint.name}"
        super().__init__(
            message,
            "constraint_violation",
            {
                "constraint_name": constraint.name,
                "constraint_type": constraint.constraint_type,
                "is_hard_constraint": constraint.is_hard_constraint,
                "violation_details": violation_details,
            },
        )


class DataIntegrityError(SchedulingException):
    """Raised when data integrity issues are detected"""

    def __init__(self, data_type, integrity_issues, message=None):
        self.data_type = data_type
        self.integrity_issues = integrity_issues

        message = (
            message
            or f"Data integrity issues found in {data_type}: {len(integrity_issues)} issues"
        )
        super().__init__(
            message,
            "data_integrity_error",
            {
                "data_type": data_type,
                "issues_count": len(integrity_issues),
                "issues": integrity_issues,
            },
        )


class SubstituteNotAvailableError(SchedulingException):
    """Raised when no substitute teacher is available"""

    def __init__(self, original_timetable, date, reason, message=None):
        self.original_timetable = original_timetable
        self.date = date
        self.reason = reason

        message = (
            message
            or f"No substitute available for {original_timetable} on {date}: {reason}"
        )
        super().__init__(
            message,
            "substitute_not_available",
            {
                "original_timetable": str(original_timetable),
                "date": date.isoformat(),
                "reason": reason,
            },
        )


class TermNotActiveError(SchedulingException):
    """Raised when trying to operate on an inactive term"""

    def __init__(self, term, operation, message=None):
        self.term = term
        self.operation = operation

        message = message or f"Cannot perform {operation} on inactive term {term}"
        super().__init__(
            message,
            "term_not_active",
            {"term": str(term), "operation": operation, "term_status": "inactive"},
        )


# Custom exception handler for DRF
def custom_scheduling_exception_handler(exc, context):
    """Custom exception handler for scheduling module exceptions"""

    # Call DRF's default exception handler first
    response = exception_handler(exc, context)

    # Handle custom scheduling exceptions
    if isinstance(exc, SchedulingException):
        error_data = {
            "error": True,
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        }

        # Determine HTTP status code based on exception type
        if isinstance(exc, TimetableConflictError):
            status_code = status.HTTP_409_CONFLICT
        elif isinstance(exc, OptimizationError):
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        elif isinstance(exc, (TeacherUnavailableError, RoomUnavailableError)):
            status_code = status.HTTP_409_CONFLICT
        elif isinstance(exc, (InvalidTimeSlotError, InvalidSubjectAssignmentError)):
            status_code = status.HTTP_400_BAD_REQUEST
        elif isinstance(exc, TimetableGenerationInProgressError):
            status_code = status.HTTP_423_LOCKED
        elif isinstance(exc, DataIntegrityError):
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        response = Response(error_data, status=status_code)

    return response


# Utility functions for exception handling
def validate_timetable_assignment(
    class_assigned, subject, teacher, time_slot, term, room=None
):
    """
    Validate a timetable assignment and raise appropriate exceptions

    Args:
        class_assigned: Class object
        subject: Subject object
        teacher: Teacher object
        time_slot: TimeSlot object
        term: Term object
        room: Room object (optional)

    Raises:
        Various scheduling exceptions if validation fails
    """

    # Check if term is active
    if not term.is_current:
        raise TermNotActiveError(term, "timetable_assignment")

    # Check if time slot is valid
    if not time_slot.is_active:
        raise InvalidTimeSlotError(time_slot, "time slot is inactive")

    if time_slot.is_break:
        raise InvalidTimeSlotError(time_slot, "cannot assign classes during break time")

    # Check teacher assignment validity
    from teachers.models import TeacherClassAssignment

    teacher_assignment = TeacherClassAssignment.objects.filter(
        teacher=teacher,
        class_assigned=class_assigned,
        subject=subject,
        term=term,
        is_active=True,
    ).first()

    if not teacher_assignment:
        raise InvalidSubjectAssignmentError(
            teacher,
            subject,
            class_assigned,
            "teacher is not assigned to teach this subject to this class",
        )

    # Check for conflicts
    from .services.timetable_service import TimetableService

    conflicts = TimetableService.check_conflicts(
        teacher=teacher,
        room=room,
        class_obj=class_assigned,
        time_slot=time_slot,
        date_range=(term.start_date, term.end_date),
    )

    if conflicts:
        # Raise specific conflict exceptions
        teacher_conflicts = [c for c in conflicts if c["type"] == "teacher"]
        room_conflicts = [c for c in conflicts if c["type"] == "room"]
        class_conflicts = [c for c in conflicts if c["type"] == "class"]

        if teacher_conflicts:
            raise TeacherConflictError(teacher, time_slot, teacher_conflicts)

        if room_conflicts and room:
            raise RoomConflictError(room, time_slot, room_conflicts)

        if class_conflicts:
            raise ClassConflictError(class_assigned, time_slot, class_conflicts)


def handle_optimization_errors(func):
    """
    Decorator to handle optimization errors gracefully

    Usage:
        @handle_optimization_errors
        def my_optimization_function():
            # optimization code
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if isinstance(e, SchedulingException):
                raise
            else:
                # Convert generic exceptions to optimization errors
                raise OptimizationError(
                    reason=str(e),
                    message=f"Optimization failed due to unexpected error: {str(e)}",
                )

    return wrapper


def safe_timetable_operation(func):
    """
    Decorator to safely handle timetable operations with proper error handling

    Usage:
        @safe_timetable_operation
        def my_timetable_function():
            # timetable operation code
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            # Convert Django validation errors to scheduling exceptions
            raise SchedulingException(
                message=str(e),
                code="validation_error",
                details={
                    "validation_errors": (
                        e.message_dict if hasattr(e, "message_dict") else str(e)
                    )
                },
            )
        except SchedulingException:
            # Re-raise scheduling exceptions as-is
            raise
        except Exception as e:
            # Convert other exceptions to generic scheduling exceptions
            raise SchedulingException(
                message=f"Unexpected error in timetable operation: {str(e)}",
                code="unexpected_error",
            )

    return wrapper


# Exception logging utilities
import logging

logger = logging.getLogger("scheduling.exceptions")


def log_scheduling_exception(exc, context=None):
    """
    Log scheduling exceptions with appropriate detail level

    Args:
        exc: The exception to log
        context: Additional context information
    """

    context = context or {}

    if isinstance(exc, TimetableConflictError):
        logger.warning(
            f"Timetable conflict: {exc.message}",
            extra={"conflicts": exc.conflicts, "context": context},
        )
    elif isinstance(exc, OptimizationError):
        logger.error(
            f"Optimization error: {exc.message}",
            extra={
                "reason": exc.reason,
                "failed_assignments_count": len(exc.failed_assignments),
                "context": context,
            },
        )
    elif isinstance(exc, ConstraintViolationError):
        logger.warning(
            f"Constraint violation: {exc.message}",
            extra={
                "constraint": exc.constraint.name,
                "violation_details": exc.violation_details,
                "context": context,
            },
        )
    else:
        logger.error(
            f"Scheduling error: {exc.message}",
            extra={"code": exc.code, "details": exc.details, "context": context},
        )
