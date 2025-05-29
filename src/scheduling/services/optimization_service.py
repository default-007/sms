import copy
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Count, Q

from src.academics.models import Class, Grade, Term
from src.subjects.models import Subject
from src.teachers.models import Teacher, TeacherClassAssignment

from ..models import (
    Room,
    SchedulingConstraint,
    TimeSlot,
    Timetable,
    TimetableGeneration,
)


@dataclass
class SchedulingSlot:
    """Data structure for scheduling slots"""

    time_slot: TimeSlot
    class_obj: Class
    subject: Subject
    teacher: Teacher = None
    room: Room = None
    priority: int = 5
    is_assigned: bool = False


@dataclass
class SchedulingResult:
    """Result of scheduling optimization"""

    success: bool
    assigned_slots: List[SchedulingSlot]
    unassigned_slots: List[SchedulingSlot]
    conflicts: List[Dict]
    optimization_score: float
    execution_time: float


class OptimizationService:
    """Advanced timetable optimization using genetic algorithm"""

    def __init__(self, term: Term):
        self.term = term
        self.constraints = self._load_constraints()
        self.time_slots = list(TimeSlot.objects.filter(is_active=True, is_break=False))
        self.rooms = list(Room.objects.filter(is_available=True))

    def _load_constraints(self) -> List[SchedulingConstraint]:
        """Load active scheduling constraints"""
        return list(
            SchedulingConstraint.objects.filter(is_active=True).order_by("-priority")
        )

    def generate_optimized_timetable(
        self,
        grades: List[Grade],
        algorithm: str = "genetic",
        population_size: int = 50,
        generations: int = 100,
        mutation_rate: float = 0.1,
    ) -> SchedulingResult:
        """Generate optimized timetable using specified algorithm"""

        start_time = datetime.now()

        # Get required scheduling slots
        required_slots = self._get_required_slots(grades)

        if algorithm == "genetic":
            result = self._genetic_algorithm(
                required_slots, population_size, generations, mutation_rate
            )
        elif algorithm == "greedy":
            result = self._greedy_algorithm(required_slots)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        execution_time = (datetime.now() - start_time).total_seconds()
        result.execution_time = execution_time

        return result

    def _get_required_slots(self, grades: List[Grade]) -> List[SchedulingSlot]:
        """Get all required scheduling slots for given grades"""
        slots = []

        for grade in grades:
            classes = Class.objects.filter(
                grade=grade, academic_year=self.term.academic_year
            )

            for class_obj in classes:
                assignments = TeacherClassAssignment.objects.filter(
                    class_assigned=class_obj, term=self.term, is_active=True
                ).select_related("teacher", "subject")

                for assignment in assignments:
                    # Calculate required periods per week based on subject credit hours
                    periods_per_week = getattr(assignment.subject, "credit_hours", 5)

                    for _ in range(periods_per_week):
                        slot = SchedulingSlot(
                            time_slot=None,  # To be assigned
                            class_obj=class_obj,
                            subject=assignment.subject,
                            teacher=assignment.teacher,
                            priority=self._calculate_subject_priority(
                                assignment.subject
                            ),
                        )
                        slots.append(slot)

        return slots

    def _calculate_subject_priority(self, subject: Subject) -> int:
        """Calculate subject priority for scheduling"""
        priority_map = {
            "mathematics": 9,
            "english": 9,
            "science": 8,
            "physics": 8,
            "chemistry": 8,
            "biology": 8,
            "history": 7,
            "geography": 7,
            "computer": 6,
            "art": 5,
            "music": 5,
            "physical_education": 4,
        }

        subject_name_lower = subject.name.lower()
        for key, priority in priority_map.items():
            if key in subject_name_lower:
                return priority

        return 5  # Default priority

    def _genetic_algorithm(
        self,
        required_slots: List[SchedulingSlot],
        population_size: int,
        generations: int,
        mutation_rate: float,
    ) -> SchedulingResult:
        """Genetic algorithm for timetable optimization"""

        # Initialize population
        population = []
        for _ in range(population_size):
            individual = self._create_random_schedule(required_slots.copy())
            population.append(individual)

        best_individual = None
        best_fitness = float("-inf")

        for generation in range(generations):
            # Evaluate fitness
            fitness_scores = []
            for individual in population:
                fitness = self._calculate_fitness(individual)
                fitness_scores.append(fitness)

                if fitness > best_fitness:
                    best_fitness = fitness
                    best_individual = copy.deepcopy(individual)

            # Selection and crossover
            new_population = []
            for _ in range(population_size):
                parent1 = self._tournament_selection(population, fitness_scores)
                parent2 = self._tournament_selection(population, fitness_scores)

                child = self._crossover(parent1, parent2)

                if random.random() < mutation_rate:
                    child = self._mutate(child)

                new_population.append(child)

            population = new_population

        # Analyze best solution
        assigned_slots = [slot for slot in best_individual if slot.is_assigned]
        unassigned_slots = [slot for slot in best_individual if not slot.is_assigned]
        conflicts = self._detect_conflicts(assigned_slots)

        return SchedulingResult(
            success=len(unassigned_slots) == 0,
            assigned_slots=assigned_slots,
            unassigned_slots=unassigned_slots,
            conflicts=conflicts,
            optimization_score=best_fitness,
            execution_time=0,  # Will be set by caller
        )

    def _create_random_schedule(
        self, slots: List[SchedulingSlot]
    ) -> List[SchedulingSlot]:
        """Create a random schedule assignment"""

        # Sort by priority
        slots.sort(key=lambda x: x.priority, reverse=True)

        # Track assignments
        teacher_schedule = {}  # teacher_id -> {(day, period): slot}
        room_schedule = {}  # room_id -> {(day, period): slot}
        class_schedule = {}  # class_id -> {(day, period): slot}

        for slot in slots:
            best_assignment = None
            best_score = -1

            for time_slot in self.time_slots:
                day_period = (time_slot.day_of_week, time_slot.period_number)

                # Check conflicts
                teacher_conflict = teacher_schedule.get(slot.teacher.id, {}).get(
                    day_period
                )
                class_conflict = class_schedule.get(slot.class_obj.id, {}).get(
                    day_period
                )

                if teacher_conflict or class_conflict:
                    continue

                # Find suitable room
                suitable_room = self._find_suitable_room(
                    slot, day_period, room_schedule
                )

                if suitable_room:
                    # Calculate assignment score
                    score = self._calculate_assignment_score(
                        slot, time_slot, suitable_room
                    )

                    if score > best_score:
                        best_score = score
                        best_assignment = (time_slot, suitable_room)

            # Assign if possible
            if best_assignment:
                time_slot, room = best_assignment
                day_period = (time_slot.day_of_week, time_slot.period_number)

                slot.time_slot = time_slot
                slot.room = room
                slot.is_assigned = True

                # Update tracking
                if slot.teacher.id not in teacher_schedule:
                    teacher_schedule[slot.teacher.id] = {}
                teacher_schedule[slot.teacher.id][day_period] = slot

                if room.id not in room_schedule:
                    room_schedule[room.id] = {}
                room_schedule[room.id][day_period] = slot

                if slot.class_obj.id not in class_schedule:
                    class_schedule[slot.class_obj.id] = {}
                class_schedule[slot.class_obj.id][day_period] = slot

        return slots

    def _find_suitable_room(
        self, slot: SchedulingSlot, day_period: Tuple[int, int], room_schedule: Dict
    ) -> Optional[Room]:
        """Find suitable room for a slot"""

        # Room requirements based on subject
        subject_room_preferences = {
            "science": ["laboratory", "classroom"],
            "physics": ["laboratory", "classroom"],
            "chemistry": ["laboratory", "classroom"],
            "biology": ["laboratory", "classroom"],
            "computer": ["computer_lab", "classroom"],
            "physical_education": ["gymnasium", "outdoor"],
            "music": ["music_room", "classroom"],
            "art": ["art_room", "classroom"],
        }

        subject_name_lower = slot.subject.name.lower()
        preferred_types = ["classroom"]  # Default

        for key, types in subject_room_preferences.items():
            if key in subject_name_lower:
                preferred_types = types
                break

        # Find available rooms
        for room in self.rooms:
            # Check if room is free
            if room.id in room_schedule and day_period in room_schedule[room.id]:
                continue

            # Check capacity
            class_size = getattr(slot.class_obj, "student_count", 30)
            if room.capacity < class_size:
                continue

            # Check room type preference
            if room.room_type in preferred_types:
                return room

        # Fallback to any available classroom
        for room in self.rooms:
            if room.id in room_schedule and day_period in room_schedule[room.id]:
                continue

            class_size = getattr(slot.class_obj, "student_count", 30)
            if room.capacity >= class_size:
                return room

        return None

    def _calculate_assignment_score(
        self, slot: SchedulingSlot, time_slot: TimeSlot, room: Room
    ) -> float:
        """Calculate score for a potential assignment"""

        score = 0.0

        # Time preferences (morning for core subjects)
        if slot.priority >= 8 and time_slot.period_number <= 3:
            score += 20
        elif slot.priority <= 5 and time_slot.period_number >= 5:
            score += 15

        # Room suitability
        subject_name_lower = slot.subject.name.lower()
        if "science" in subject_name_lower and room.room_type == "laboratory":
            score += 25
        elif "computer" in subject_name_lower and room.room_type == "computer_lab":
            score += 25
        elif "physical" in subject_name_lower and room.room_type in [
            "gymnasium",
            "outdoor",
        ]:
            score += 25

        # Capacity efficiency
        class_size = getattr(slot.class_obj, "student_count", 30)
        capacity_ratio = class_size / room.capacity
        if 0.7 <= capacity_ratio <= 1.0:
            score += 15
        elif capacity_ratio > 1.0:
            score -= 30  # Overcrowded

        return score

    def _calculate_fitness(self, schedule: List[SchedulingSlot]) -> float:
        """Calculate fitness score for a schedule"""

        score = 0.0
        assigned_count = sum(1 for slot in schedule if slot.is_assigned)
        total_count = len(schedule)

        # Assignment completion (40% of score)
        assignment_ratio = assigned_count / total_count if total_count > 0 else 0
        score += assignment_ratio * 400

        # Conflict penalty (30% of score)
        assigned_slots = [slot for slot in schedule if slot.is_assigned]
        conflicts = self._detect_conflicts(assigned_slots)
        conflict_penalty = len(conflicts) * 30
        score -= conflict_penalty

        # Constraint satisfaction (30% of score)
        constraint_score = self._evaluate_constraints(assigned_slots)
        score += constraint_score * 300

        return score

    def _detect_conflicts(self, slots: List[SchedulingSlot]) -> List[Dict]:
        """Detect conflicts in assigned slots"""

        conflicts = []

        # Group by time slot
        time_slot_assignments = {}
        for slot in slots:
            if not slot.time_slot:
                continue

            key = (slot.time_slot.day_of_week, slot.time_slot.period_number)
            if key not in time_slot_assignments:
                time_slot_assignments[key] = []
            time_slot_assignments[key].append(slot)

        # Check for conflicts
        for time_key, slot_list in time_slot_assignments.items():
            if len(slot_list) <= 1:
                continue

            # Teacher conflicts
            teachers = {}
            for slot in slot_list:
                if slot.teacher.id in teachers:
                    conflicts.append(
                        {
                            "type": "teacher",
                            "teacher": slot.teacher,
                            "time_slot": slot.time_slot,
                            "conflicting_classes": [
                                teachers[slot.teacher.id].class_obj,
                                slot.class_obj,
                            ],
                        }
                    )
                teachers[slot.teacher.id] = slot

            # Room conflicts
            rooms = {}
            for slot in slot_list:
                if slot.room and slot.room.id in rooms:
                    conflicts.append(
                        {
                            "type": "room",
                            "room": slot.room,
                            "time_slot": slot.time_slot,
                            "conflicting_classes": [
                                rooms[slot.room.id].class_obj,
                                slot.class_obj,
                            ],
                        }
                    )
                if slot.room:
                    rooms[slot.room.id] = slot

        return conflicts

    def _evaluate_constraints(self, slots: List[SchedulingSlot]) -> float:
        """Evaluate constraint satisfaction"""

        total_score = 0.0
        total_weight = 0.0

        for constraint in self.constraints:
            weight = constraint.priority / 10.0
            total_weight += weight

            satisfaction = self._evaluate_single_constraint(constraint, slots)
            total_score += satisfaction * weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def _evaluate_single_constraint(
        self, constraint: SchedulingConstraint, slots: List[SchedulingSlot]
    ) -> float:
        """Evaluate a single constraint"""

        if constraint.constraint_type == "teacher_availability":
            return self._evaluate_teacher_availability(constraint, slots)
        elif constraint.constraint_type == "consecutive_periods":
            return self._evaluate_consecutive_periods(constraint, slots)
        elif constraint.constraint_type == "daily_limit":
            return self._evaluate_daily_limit(constraint, slots)
        elif constraint.constraint_type == "time_preference":
            return self._evaluate_time_preference(constraint, slots)

        return 1.0  # Default satisfaction

    def _evaluate_teacher_availability(
        self, constraint: SchedulingConstraint, slots: List[SchedulingSlot]
    ) -> float:
        """Evaluate teacher availability constraint"""

        # Implementation depends on constraint parameters
        # For now, return high satisfaction if no obvious violations
        return 0.9

    def _evaluate_consecutive_periods(
        self, constraint: SchedulingConstraint, slots: List[SchedulingSlot]
    ) -> float:
        """Evaluate consecutive periods constraint"""

        # Check for subjects that should/shouldn't be consecutive
        subject_groups = {}
        for slot in slots:
            if not slot.time_slot:
                continue

            key = (slot.class_obj.id, slot.time_slot.day_of_week)
            if key not in subject_groups:
                subject_groups[key] = []
            subject_groups[key].append(slot)

        satisfaction = 0.0
        count = 0

        for group in subject_groups.values():
            group.sort(key=lambda x: x.time_slot.period_number)

            for i in range(len(group) - 1):
                current = group[i]
                next_slot = group[i + 1]

                # Check if consecutive periods are appropriate
                if (
                    abs(
                        current.time_slot.period_number
                        - next_slot.time_slot.period_number
                    )
                    == 1
                ):
                    # Same subject consecutive - good for labs, bad for regular classes
                    if current.subject == next_slot.subject:
                        if "lab" in current.subject.name.lower():
                            satisfaction += 1.0
                        else:
                            satisfaction += 0.3
                    else:
                        satisfaction += 0.8  # Different subjects - generally good

                count += 1

        return satisfaction / count if count > 0 else 1.0

    def _evaluate_daily_limit(
        self, constraint: SchedulingConstraint, slots: List[SchedulingSlot]
    ) -> float:
        """Evaluate daily subject limit constraint"""

        # Count subjects per day per class
        daily_counts = {}
        for slot in slots:
            if not slot.time_slot:
                continue

            key = (slot.class_obj.id, slot.time_slot.day_of_week, slot.subject.id)
            daily_counts[key] = daily_counts.get(key, 0) + 1

        violations = sum(1 for count in daily_counts.values() if count > 2)
        total_assignments = len([s for s in slots if s.time_slot])

        return (
            max(0.0, 1.0 - (violations / total_assignments))
            if total_assignments > 0
            else 1.0
        )

    def _evaluate_time_preference(
        self, constraint: SchedulingConstraint, slots: List[SchedulingSlot]
    ) -> float:
        """Evaluate time preference constraint"""

        # Core subjects should be in morning periods
        core_subjects = ["mathematics", "english", "science"]
        satisfaction = 0.0
        count = 0

        for slot in slots:
            if not slot.time_slot:
                continue

            subject_name_lower = slot.subject.name.lower()
            is_core = any(core in subject_name_lower for core in core_subjects)

            if is_core and slot.time_slot.period_number <= 3:
                satisfaction += 1.0
            elif not is_core and slot.time_slot.period_number > 3:
                satisfaction += 1.0
            else:
                satisfaction += 0.5

            count += 1

        return satisfaction / count if count > 0 else 1.0

    def _tournament_selection(
        self,
        population: List[List[SchedulingSlot]],
        fitness_scores: List[float],
        tournament_size: int = 3,
    ) -> List[SchedulingSlot]:
        """Tournament selection for genetic algorithm"""

        tournament_indices = random.sample(range(len(population)), tournament_size)
        best_index = max(tournament_indices, key=lambda i: fitness_scores[i])

        return copy.deepcopy(population[best_index])

    def _crossover(
        self, parent1: List[SchedulingSlot], parent2: List[SchedulingSlot]
    ) -> List[SchedulingSlot]:
        """Crossover operation for genetic algorithm"""

        child = copy.deepcopy(parent1)

        # Randomly swap some assignments from parent2
        for i in range(len(child)):
            if random.random() < 0.3:  # 30% chance to inherit from parent2
                if i < len(parent2) and parent2[i].is_assigned:
                    # Check if we can safely inherit this assignment
                    if not self._would_create_conflict(child, i, parent2[i]):
                        child[i].time_slot = parent2[i].time_slot
                        child[i].room = parent2[i].room
                        child[i].is_assigned = parent2[i].is_assigned

        return child

    def _would_create_conflict(
        self, schedule: List[SchedulingSlot], index: int, new_assignment: SchedulingSlot
    ) -> bool:
        """Check if assignment would create conflict"""

        if not new_assignment.time_slot:
            return False

        day_period = (
            new_assignment.time_slot.day_of_week,
            new_assignment.time_slot.period_number,
        )

        for i, slot in enumerate(schedule):
            if i == index or not slot.is_assigned or not slot.time_slot:
                continue

            other_day_period = (
                slot.time_slot.day_of_week,
                slot.time_slot.period_number,
            )
            if day_period == other_day_period:
                # Check for teacher or room conflict
                if slot.teacher == new_assignment.teacher or (
                    slot.room
                    and new_assignment.room
                    and slot.room == new_assignment.room
                ):
                    return True

        return False

    def _mutate(self, individual: List[SchedulingSlot]) -> List[SchedulingSlot]:
        """Mutation operation for genetic algorithm"""

        mutated = copy.deepcopy(individual)

        # Randomly reassign some slots
        for slot in mutated:
            if random.random() < 0.1:  # 10% mutation rate per slot
                if slot.is_assigned:
                    # Try to find alternative assignment
                    available_slots = [
                        ts
                        for ts in self.time_slots
                        if not self._would_create_time_conflict(mutated, slot, ts)
                    ]

                    if available_slots:
                        new_time_slot = random.choice(available_slots)
                        new_room = self._find_suitable_room(
                            slot,
                            (new_time_slot.day_of_week, new_time_slot.period_number),
                            {},
                        )

                        if new_room:
                            slot.time_slot = new_time_slot
                            slot.room = new_room

        return mutated

    def _would_create_time_conflict(
        self,
        schedule: List[SchedulingSlot],
        target_slot: SchedulingSlot,
        new_time_slot: TimeSlot,
    ) -> bool:
        """Check if new time slot would create conflict"""

        day_period = (new_time_slot.day_of_week, new_time_slot.period_number)

        for slot in schedule:
            if slot == target_slot or not slot.is_assigned or not slot.time_slot:
                continue

            other_day_period = (
                slot.time_slot.day_of_week,
                slot.time_slot.period_number,
            )
            if day_period == other_day_period:
                if slot.teacher == target_slot.teacher:
                    return True

        return False

    def _greedy_algorithm(
        self, required_slots: List[SchedulingSlot]
    ) -> SchedulingResult:
        """Simple greedy algorithm for comparison"""

        # Sort by priority
        required_slots.sort(key=lambda x: x.priority, reverse=True)

        assigned_slots = []
        unassigned_slots = []

        # Simple assignment
        schedule = self._create_random_schedule(required_slots)

        for slot in schedule:
            if slot.is_assigned:
                assigned_slots.append(slot)
            else:
                unassigned_slots.append(slot)

        conflicts = self._detect_conflicts(assigned_slots)
        fitness = self._calculate_fitness(schedule)

        return SchedulingResult(
            success=len(unassigned_slots) == 0,
            assigned_slots=assigned_slots,
            unassigned_slots=unassigned_slots,
            conflicts=conflicts,
            optimization_score=fitness,
            execution_time=0,
        )

    @transaction.atomic
    def save_schedule_to_database(
        self, result: SchedulingResult, created_by: "User" = None
    ) -> Dict[str, int]:
        """Save optimized schedule to database"""

        created_count = 0
        errors = []

        # Clear existing timetable for the term
        Timetable.objects.filter(term=self.term).delete()

        for slot in result.assigned_slots:
            try:
                timetable = Timetable.objects.create(
                    class_assigned=slot.class_obj,
                    subject=slot.subject,
                    teacher=slot.teacher,
                    time_slot=slot.time_slot,
                    room=slot.room,
                    term=self.term,
                    effective_from_date=self.term.start_date,
                    effective_to_date=self.term.end_date,
                    created_by=created_by,
                )
                created_count += 1

            except Exception as e:
                errors.append(f"Error saving {slot}: {str(e)}")

        return {
            "created": created_count,
            "errors": errors,
            "unassigned_count": len(result.unassigned_slots),
        }
