
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.dateparse import parse_date, parse_datetime
from django.db import transaction
from django.db.models import Q
import uuid
from django.utils import timezone
from django.db import IntegrityError
import uuid
from django.utils import timezone

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
# Расписание и запись пациента
@login_required(login_url='bxod')
def table(request):
    profile = UserProfile.objects.filter(user=request.user).first()

    if request.user.is_superuser:
        role = 'admin'
    elif profile:
        role = profile.role
    else:
        role = 'unknown'

    # Обработка нажатия кнопки «Записаться»
    if request.method == 'POST':
        if role != 'patient':
            messages.error(request, 'Записываться на приём могут только пациенты.')
            return redirect('table')

        patient = PatientProfile.objects.filter(user=request.user).first()

        if not patient:
            messages.error(request, 'Профиль пациента не найден.')
            return redirect('table')

        slot_id = request.POST.get('slot_id')

        try:
            with transaction.atomic():
                slot = TimeSlot.objects.select_for_update().get(
                    id=slot_id,
                    is_available=True
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

                    messages.success(
                        request,
                        'Вы успешно записались! Электронный талон создан.'
                    )

        except (TimeSlot.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'Это время уже недоступно для записи.')

        return redirect('table')

    # Свободное время
    free_slots = TimeSlot.objects.filter(
        is_available=True,
        start_time__gte=timezone.now()
    ).select_related(
        'doctor__user',
        'doctor__specialty'
    ).order_by('start_time')

    # Записи в зависимости от роли
    if role == 'patient':
        patient = PatientProfile.objects.filter(user=request.user).first()

        appointments = Appointment.objects.filter(
            patient=patient
        ) if patient else Appointment.objects.none()

    elif role == 'doctor':
        doctor = DoctorProfile.objects.filter(user=request.user).first()

        appointments = Appointment.objects.filter(
            slot__doctor=doctor
        ) if doctor else Appointment.objects.none()

    elif role == 'admin':
        appointments = Appointment.objects.all()

    else:
        appointments = Appointment.objects.none()

    appointments = appointments.select_related(
        'patient__user',
        'slot__doctor__user',
        'slot__doctor__specialty'
    )

    return render(request, 'table.html', {
        'free_slots': free_slots,
        'appointments': appointments,
        'role': role,
    })

# Выход из аккаунта
@login_required(login_url='bxod')
def logout_view(request):
    logout(request)
    return redirect('main')


# Управление расписанием для администратора
@login_required(login_url='bxod')
def manage_schedule(request):
    profile = UserProfile.objects.filter(user=request.user).first()

    # Проверяем права администратора
    if not request.user.is_superuser and (
        not profile or profile.role != 'admin'
    ):
        return redirect('lk')

    error = ''

    if request.method == 'POST':
        action = request.POST.get('action')

        # Удаление свободного времени
        if action == 'delete':
            slot_id = request.POST.get('slot_id')

            slot = TimeSlot.objects.filter(
                id=slot_id,
                is_available=True
            ).first()

            if slot and not Appointment.objects.filter(slot=slot).exists():
                slot.delete()
                messages.success(request, 'Свободное время удалено.')
            else:
                messages.error(
                    request,
                    'Нельзя удалить занятое или несуществующее время.'
                )

            return redirect('manage_schedule')

        # Добавление нового времени
        if action == 'add':
            doctor_id = request.POST.get('doctor')
            start_text = request.POST.get('start_time')
            end_text = request.POST.get('end_time')

            doctor = DoctorProfile.objects.filter(
                id=doctor_id
            ).first()

            start_time = parse_datetime(start_text)
            end_time = parse_datetime(end_text)

            if not doctor:
                error = 'Выберите врача.'

            elif not start_time or not end_time:
                error = 'Укажите корректные дату и время.'

            else:
                if timezone.is_naive(start_time):
                    start_time = timezone.make_aware(start_time)

                if timezone.is_naive(end_time):
                    end_time = timezone.make_aware(end_time)

                if start_time <= timezone.now():
                    error = 'Нельзя добавить время в прошлом.'

                elif end_time <= start_time:
                    error = 'Время окончания должно быть позже начала.'

                elif TimeSlot.objects.filter(
                    doctor=doctor,
                    start_time__lt=end_time,
                    end_time__gt=start_time
                ).exists():
                    error = 'У этого врача уже есть пересекающееся время.'

                else:
                    TimeSlot.objects.create(
                        doctor=doctor,
                        start_time=start_time,
                        end_time=end_time,
                        is_available=True
                    )

                    messages.success(request, 'Новое время добавлено!')
                    return redirect('manage')

    doctors = DoctorProfile.objects.select_related(
        'user',
        'specialty'
    ).all()

    slots = TimeSlot.objects.select_related(
        'doctor__user',
        'doctor__specialty'
    ).order_by('start_time')

    return render(request, 'manage.html', {
        'doctors': doctors,
        'slots': slots,
        'error': error,
    })


@login_required(login_url='bxod')
def manage_doctors(request):
    profile = UserProfile.objects.filter(user=request.user).first()

    # Проверка прав администратора
    if not request.user.is_superuser and (
        not profile or profile.role != 'admin'
    ):
        return redirect('lk')

    error = ''

    if request.method == 'POST':
        action = request.POST.get('action')

        # Добавление специальности
        if action == 'add_specialty':
            specialty_name = request.POST.get('specialty_name', '').strip()
            specialty_description = request.POST.get(
                'specialty_description', ''
            ).strip()

            if not specialty_name:
                error = 'Введите название специальности.'
            elif Specialty.objects.filter(
                name__iexact=specialty_name
            ).exists():
                error = 'Такая специальность уже существует.'
            else:
                Specialty.objects.create(
                    name=specialty_name,
                    description=specialty_description
                )
                messages.success(request, 'Специальность добавлена!')
                return redirect('manage_doctors')

        # Добавление врача
        elif action == 'add_doctor':
            username = request.POST.get('username', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip().lower()
            password = request.POST.get('password', '')
            phone = request.POST.get('phone', '').strip()
            experience_text = request.POST.get('experience', '0').strip()
            room = request.POST.get('room', '').strip()
            description = request.POST.get('description', '').strip()
            specialty_id = request.POST.get('specialty', '')

            specialty = Specialty.objects.filter(
                id=specialty_id
            ).first()

            if not all([username, first_name, last_name, email, password]):
                error = 'Заполните все обязательные поля.'
            elif User.objects.filter(username__iexact=username).exists():
                error = 'Такой логин уже занят.'
            elif User.objects.filter(email__iexact=email).exists():
                error = 'Такая почта уже зарегистрирована.'
            elif not specialty:
                error = 'Выберите специальность.'
            else:
                try:
                    experience = int(experience_text)

                    if experience < 0:
                        error = 'Стаж не может быть отрицательным.'
                except ValueError:
                    experience = 0
                    error = 'Укажите корректный стаж.'

                if not error:
                    with transaction.atomic():
                        user = User.objects.create_user(
                            username=username,
                            password=password,
                            first_name=first_name,
                            last_name=last_name,
                            email=email
                        )

                        UserProfile.objects.create(
                            user=user,
                            role='doctor'
                        )

                        DoctorProfile.objects.create(
                            user=user,
                            specialty=specialty,
                            phone=phone,
                            experience=experience,
                            room=room,
                            description=description
                        )

                    messages.success(request, 'Врач успешно добавлен!')
                    return redirect('manage_doctors')

    doctors = DoctorProfile.objects.select_related(
        'user', 'specialty'
    ).all()

    specialties = Specialty.objects.all()

    return render(request, 'managed.html', {
        'doctors': doctors,
        'specialties': specialties,
        'error': error,
    })


