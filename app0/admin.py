
from django.contrib import admin
from .models import (
    UserProfile,
    Specialty,
    PatientProfile,
    DoctorProfile,
    TimeSlot,
    Appointment,
    MedicalRecord,
    Prescription,
    Attachment,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'birth_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialty', 'phone', 'experience', 'room')
    list_filter = ('specialty',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'start_time', 'end_time', 'is_available')
    list_filter = ('is_available', 'doctor')
    search_fields = ('doctor__user__username',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'patient', 'slot', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = (
        'ticket_number',
        'patient__user__username',
        'slot__doctor__user__username',
    )


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'diagnosis', 'created_at')
    search_fields = ('diagnosis', 'appointment__ticket_number')


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('medication', 'dosage', 'medical_record', 'created_at')
    search_fields = ('medication',)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'uploaded_by', 'file', 'uploaded_at')
    list_filter = ('uploaded_at',)

