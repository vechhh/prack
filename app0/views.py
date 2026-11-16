
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date
from django.db import transaction
from django.db.models import Q
import uuid
from django.utils import timezone
from django.db import IntegrityError

from .models import (
    UserProfile,
    PatientProfile,
    DoctorProfile,
    Appointment,
    Specialty,
    TimeSlot,
)

# Главная страница
def main(request):
    return render(request, 'main.html')


# Каталог врачей
def med(request):
    doctors = DoctorProfile.objects.select_related(
        'user', 'specialty'
    ).all()

    search = request.GET.get('search', '').strip()
    specialty = request.GET.get('specialty', '').strip()

    if search:
        doctors = doctors.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )

    if specialty:
        doctors = doctors.filter(specialty_id=specialty)

    specialties = Specialty.objects.all()

    return render(request, 'med.html', {
        'doctors': doctors,
        'specialties': specialties,
        'search': search,
        'selected_specialty': specialty,
    })


# Регистрация пациента
def regist(request):
    if request.user.is_authenticated:
        return redirect('lk')

    error = ''

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        birth_date_text = request.POST.get('birth_date', '').strip()
        address = request.POST.get('address', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not all([
            username, first_name, last_name,
            email, phone, password1, password2
        ]):
            error = 'Заполните все обязательные поля.'

        elif User.objects.filter(username__iexact=username).exists():
            error = 'Такой логин уже занят.'

        elif User.objects.filter(email__iexact=email).exists():
            error = 'Такая электронная почта уже зарегистрирована.'

        elif password1 != password2:
            error = 'Пароли не совпадают.'

        else:
            birth_date = None

            if birth_date_text:
                birth_date = parse_date(birth_date_text)

                if birth_date is None:
                    error = 'Неверный формат даты рождения.'

            if not error:
                try:
                    validate_password(password1)
                except ValidationError as e:
                    error = ' '.join(e.messages)

            if not error:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username,
                        password=password1,
                        first_name=first_name,
                        last_name=last_name,
                        email=email
                    )

                    UserProfile.objects.create(
                        user=user,
                        role='patient'
                    )

                    PatientProfile.objects.create(
                        user=user,
                        phone=phone,
                        birth_date=birth_date,
                        address=address
                    )

                messages.success(
                    request,
                    'Регистрация прошла успешно! Теперь войдите.'
                )

                return redirect('bxod')

    return render(request, 'regist.html', {
        'error': error
    })


# Авторизация
def bxod(request):
    if request.user.is_authenticated:
        return redirect('lk')

    error = ''

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect('lk')

        error = 'Неверный логин или пароль.'

    return render(request, 'bxod.html', {
        'error': error
    })


# Личный кабинет
@login_required(login_url='bxod')
def lk(request):
    user = request.user
    profile = UserProfile.objects.filter(user=user).first()

    if user.is_superuser:
        role = 'admin'
    elif profile:
        role = profile.role
    else:
        role = 'unknown'

    context = {
        'profile': profile,
        'role': role,
    }

    if role == 'patient':
        patient = PatientProfile.objects.filter(user=user).first()
        context['patient'] = patient

        if patient:
            context['appointments'] = Appointment.objects.filter(
                patient=patient
            ).select_related(
                'slot__doctor__user',
                'slot__doctor__specialty'
            )

    elif role == 'doctor':
        doctor = DoctorProfile.objects.filter(user=user).first()
        context['doctor'] = doctor

        if doctor:
            context['appointments'] = Appointment.objects.filter(
                slot__doctor=doctor
            ).select_related(
                'patient__user',
                'slot'
            )

    elif role == 'admin':
        context['appointments'] = Appointment.objects.select_related(
            'patient__user',
            'slot__doctor__user'
        ).all()

    return render(request, 'lk.html', context)



# Таблица записей и свободное расписание
@login_required(login_url='bxod')
def table(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    patient = PatientProfile.objects.filter(user=request.user).first()

    # Обработка записи пациента
    if request.method == 'POST':
        if not profile or profile.role != 'patient' or not patient:
            messages.error(request, 'Записываться на приём могут только пациенты.')
            return redirect('table')

        slot_id = request.POST.get('slot_id', '')

        try:
            with transaction.atomic():
                slot = TimeSlot.objects.select_for_update().get(
                    pk=slot_id,
                    is_available=True,
                    start_time__gte=timezone.now()
                )

                if Appointment.objects.filter(slot=slot).exists():
                    messages.error(request, 'Это время уже занято.')
                else:
                    Appointment.objects.create(
                        patient=patient,
                        slot=slot,
                        ticket_number=uuid.uuid4().hex[:10].upper()
                    )

                    slot.is_available = False
                    slot.save(update_fields=['is_available'])

                    messages.success(request, 'Вы успешно записались на приём!')

        except (TimeSlot.DoesNotExist, ValueError, IntegrityError):
            messages.error(request, 'Не удалось записаться. Возможно, это время уже занято.')

        return redirect('table')

    # Записи текущего пользователя
    if request.user.is_superuser:
        appointments = Appointment.objects.all()

    elif profile and profile.role == 'doctor':
        doctor = DoctorProfile.objects.filter(user=request.user).first()
        appointments = Appointment.objects.filter(
            slot__doctor=doctor
        ) if doctor else Appointment.objects.none()

    elif profile and profile.role == 'patient':
        appointments = Appointment.objects.filter(
            patient=patient
        ) if patient else Appointment.objects.none()

    else:
        appointments = Appointment.objects.none()

    appointments = appointments.select_related(
        'patient__user',
        'slot__doctor__user',
        'slot__doctor__specialty'
    )

    # Все свободные будущие часы приёма
    free_slots = TimeSlot.objects.filter(
        is_available=True,
        start_time__gte=timezone.now()
    ).select_related(
        'doctor__user',
        'doctor__specialty'
    ).order_by('start_time')

    return render(request, 'table.html', {
        'appointments': appointments,
        'free_slots': free_slots,
        'role': profile.role if profile else ('admin' if request.user.is_superuser else 'unknown'),
    })

# Выход из аккаунта
@login_required(login_url='bxod')
def logout_view(request):
    logout(request)
    return redirect('main')
