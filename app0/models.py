from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('patient', 'Пациент'),
        ('doctor', 'Врач'),
        ('admin', 'Администратор'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f'{self.user.username} — {self.get_role_display()}'


class Specialty(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class PatientProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='patient_data'
    )
    phone = models.CharField(max_length=20, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f'Пациент: {self.user.get_full_name() or self.user.username}'


class DoctorProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='doctor_data'
    )
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.PROTECT,
        related_name='doctors'
    )
    phone = models.CharField(max_length=20, blank=True)
    experience = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    room = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f'Врач: {self.user.get_full_name() or self.user.username}'


class TimeSlot(models.Model):
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='time_slots'
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'start_time'],
                name='unique_doctor_start_time'
            )
        ]

    def __str__(self):
        return f'{self.doctor} — {self.start_time:%d.%m.%Y %H:%M}'


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('booked', 'Записан'),
        ('completed', 'Завершён'),
        ('cancelled', 'Отменён'),
    ]

    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.PROTECT,
        related_name='appointments'
    )
    slot = models.OneToOneField(
        TimeSlot,
        on_delete=models.PROTECT,
        related_name='appointment'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='booked'
    )
    ticket_number = models.CharField(
        max_length=30,
        unique=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Талон №{self.ticket_number}'


class MedicalRecord(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='medical_record'
    )
    diagnosis = models.TextField()
    notes = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Медицинская карта: {self.appointment.ticket_number}'


class Prescription(models.Model):
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name='prescriptions'
    )
    medication = models.CharField(max_length=200)
    dosage = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.medication


class Attachment(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )
    file = models.FileField(
        upload_to='medical_files/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
            )
        ]
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name
