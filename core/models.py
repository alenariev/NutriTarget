
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import datetime
from django.contrib.auth.signals import user_logged_in

class Recipe(models.Model):
    DIET_TYPES = [
        ('all', 'Всеядное'),
        ('vege', 'Вегетарианское'),
        ('vegan', 'Веганское'),
        ('pesca', 'Пескетарианское'),
    ]
    MEAL_TYPES = [
        ('breakfast', 'Завтрак'),
        ('snack', 'Перекус'),
        ('lunch', 'Обед'),
        ('dinner', 'Ужин'),
    ]
    title = models.CharField(max_length=200, verbose_name="Название")
    diet_type = models.CharField(max_length=10, choices=DIET_TYPES, db_index=True, verbose_name="Тип диеты")
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES, default='lunch', db_index=True, verbose_name="Прием пищи")
    calories = models.PositiveIntegerField(verbose_name="Калории на 100г")
    protein = models.FloatField(verbose_name="Белки на 100г")
    fat = models.FloatField(verbose_name="Жиры на 100г")
    carbs = models.FloatField(verbose_name="Углеводы на 100г")
    description = models.TextField(verbose_name="Состав и рецепт")
    image_url = models.URLField(blank=True, null=True, verbose_name="Ссылка на фото")

    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"

    def __str__(self):
        return f"{self.get_meal_type_display()}: {self.title}"

class Profile(models.Model):
    # Основная связь
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Антропометрия
    age = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(12), MaxValueValidator(110)], verbose_name="Возраст")
    weight = models.FloatField(null=True, blank=True, validators=[MinValueValidator(30), MaxValueValidator(300)], verbose_name="Вес")
    height = models.FloatField(null=True, blank=True, validators=[MinValueValidator(120), MaxValueValidator(250)], verbose_name="Рост")
    gender = models.CharField(max_length=10, choices=[('male', 'Мужчина'), ('female', 'Женщина')], null=True, blank=True, verbose_name="Пол")

    # Цели и предпочтения
    goal = models.CharField(max_length=20, null=True, blank=True, verbose_name="Цель")
    activity = models.FloatField(null=True, blank=True, verbose_name="Коэфф. активности")
    diet_pref = models.CharField(max_length=10, null=True, blank=True, verbose_name="Предпочтения")
    allergies = models.CharField(max_length=255, blank=True, default="", verbose_name="Аллергены")

    # Результаты расчетов (КБЖУ)
    target_kcal = models.IntegerField(default=0, verbose_name="Цель ккал")
    target_protein = models.IntegerField(default=0, blank=True)
    target_fat = models.IntegerField(default=0, blank=True)
    target_carbs = models.IntegerField(default=0, blank=True)

    # ИЗБРАННОЕ (связь многие-ко-многим)
    favorite_recipes = models.ManyToManyField(Recipe, related_name='fans', blank=True, verbose_name="Избранные рецепты")

    # ПОДПИСКА И ЛИМИТЫ
    is_subscribed = models.BooleanField(default=False, verbose_name="Премиум подписка")
    subscription_end = models.DateField(null=True, blank=True, verbose_name="Дата окончания подписки")
    last_weekly_refresh = models.DateTimeField(null=True, blank=True, verbose_name="Последнее еженедельное обновление")

    class Meta:
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"

    def __str__(self):
        return f"Профиль {self.user.username}"

    # --- ОБНОВЛЕННЫЙ МЕТОД: Проверка активной подписки ---
    @property
    def has_active_subscription(self):
        """Проверяет, активна ли платная подписка на текущий момент (для платных, которые имеют срок)"""
        if self.is_subscribed:
            if self.subscription_end:
                return self.subscription_end >= timezone.now().date()
            return True  # Предполагаем, что если is_subscribed True, но даты нет, то это пожизненная подписка
        return False

    # Может ли пользователь обновить меню (логика 1 раз в неделю)
    def can_refresh_menu(self):
        # Premium пользователи могут обновлять всегда
        if self.has_active_subscription:
            return True

        # Если это первое обновление или неделя прошла
        if not self.last_weekly_refresh:
            return True

        # Проверяем, прошла ли неделя с последнего обновления
        return timezone.now() >= self.last_weekly_refresh + datetime.timedelta(days=7)

    # Сколько дней осталось до следующего бесплатного обновления
    def days_until_next_refresh(self):
        if self.has_active_subscription:
            return 0  # Для Premium нет ограничений

        if not self.last_weekly_refresh:
            return 0  # Можно обновить сейчас

        time_until_next_refresh = (self.last_weekly_refresh + datetime.timedelta(days=7)) - timezone.now()
        if time_until_next_refresh.total_seconds() <= 0:
            return 0

        # Округляем до целых дней, прибавляя 1, чтобы показать "через 3 дня" вместо "через 2.x дня"
        return time_until_next_refresh.days + 1

# Автоматическое создание профиля при регистрации пользователя
@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    # Если профиль уже существует, но, например, был создан вручную без is_verified = False,
    # убедимся, что все новые поля инициализированы.
    # Если профиль не создан при created=True, то он должен существовать, и мы его сохраняем.
    instance.profile.save()

@receiver(user_logged_in)
def transfer_guest_data_to_profile(sender, request, user, **kwargs):
    """
    Переносит данные из сессии (гостевые) в профиль пользователя при логине/регистрации
    """
    session = request.session
    # Проверяем, есть ли в сессии данные о возрасте (как признак того, что расчет был)
    if 'age' in session:
        profile = user.profile  # У пользователя уже есть профиль благодаря сигналу post_save
        
        # Переносим основные параметры
        profile.goal = session.get('goal')
        profile.activity = float(session.get('activity', 1.2))
        profile.age = session.get('age')
        profile.weight = session.get('weight')
        profile.height = session.get('height')
        profile.gender = session.get('gender')
        profile.diet_pref = session.get('diet_pref')
        profile.allergies = session.get('allergies')

        # Сразу рассчитываем КБЖУ, чтобы профиль не был пустым
        # Импортируем внутри, чтобы не было круговой ошибки импорта
        from .logic import calculate_macros
        res = calculate_macros(profile)
        profile.target_kcal = res['kcal']
        profile.target_protein = res['p']
        profile.target_fat = res['f']
        profile.target_carbs = res['c']

        profile.save()

        # Очищаем сессию, чтобы данные не перенеслись повторно другому пользователю
        keys_to_delete = ['goal', 'activity', 'age', 'weight', 'height', 'gender', 'diet_pref', 'allergies']
        for key in keys_to_delete:
            if key in session:
                del session[key]