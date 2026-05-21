from sqlalchemy import Column, String, Integer, Float, ForeignKey, Text, Date, Boolean
from sqlalchemy.orm import relationship
from app.db import Base

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    enrollments = relationship('Enrollment', back_populates='student')

class Instructor(Base):
    __tablename__ = 'instructors'
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    courses = relationship('Course', back_populates='instructor')

class Classroom(Base):
    __tablename__ = 'classrooms'
    id = Column(Integer, primary_key=True, index=True)
    building = Column(String, nullable=False)
    room_number = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    courses = relationship('Course', back_populates='classroom')

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    instructor_id = Column(Integer, ForeignKey('instructors.id'), nullable=False)
    classroom_id = Column(Integer, ForeignKey('classrooms.id'), nullable=False)
    instructor = relationship('Instructor', back_populates='courses')
    classroom = relationship('Classroom', back_populates='courses')
    enrollments = relationship('Enrollment', back_populates='course')
    assignments = relationship('Assignment', back_populates='course')

class Enrollment(Base):
    __tablename__ = 'enrollments'
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    enrollment_date = Column(Date, nullable=False)
    student = relationship('Student', back_populates='enrollments')
    course = relationship('Course', back_populates='enrollments')
    grades = relationship('Grade', back_populates='enrollment')

class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    due_date = Column(Date, nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    course = relationship('Course', back_populates='assignments')
    grades = relationship('Grade', back_populates='assignment')

class Grade(Base):
    __tablename__ = 'grades'
    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey('enrollments.id'), nullable=False)
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=False)
    score = Column(Float, nullable=False)
    graded_at = Column(Date, nullable=False)
    enrollment = relationship('Enrollment', back_populates='grades')
    assignment = relationship('Assignment', back_populates='grades')
