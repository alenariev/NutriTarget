import re
import datetime
from django.utils import timezone
import random

def scale_ingredients(description, multiplier):
    """Пересчет граммовки ингредиентов."""
    if not description: return ""
    def replace(match):
        value = float(match.group(1))
        return f"{round(value * multiplier)}"
    return re.sub(r'(\d+(?:\.\d+)?)(?=\s*(?:г|мл|шт))', replace, description)

def generate_weekly_plan(profile_or_session, all_recipes, target_kcal, is_guest=False):
    if not is_guest:
        # Автоматическое обновление раз в неделю
        if not profile_or_session.last_weekly_refresh or timezone.now() >= profile_or_session.last_weekly_refresh + datetime.timedelta(days=7):
            profile_or_session.last_weekly_refresh = timezone.now()
            if hasattr(profile_or_session, 'save'):
                profile_or_session.save()
        
        user_seed = profile_or_session.user.id
        refresh_seed = int(profile_or_session.last_weekly_refresh.timestamp())
    else:
        user_seed = "guest"
        # Для гостей генерируем сид, основанный на начале текущей недели
        start_of_week = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
        refresh_seed = int(datetime.datetime.combine(start_of_week, datetime.time.min).timestamp())
    rng = random.Random(f"{user_seed}-{refresh_seed}")  # nosec B311
    meal_dist = {
        'breakfast': {'ratio': 0.25, 'label': 'ЗАВТРАК'},
        'snack': {'ratio': 0.15, 'label': 'ПЕРЕКУС'},
        'lunch': {'ratio': 0.35, 'label': 'ОБЕД'},
        'dinner': {'ratio': 0.25, 'label': 'УЖИН'},
    }
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    weekly_plan = []

    pools = {m: [r for r in all_recipes if r.meal_type == m] for m in meal_dist.keys()}
    
    # Проверяем, есть ли хоть какие-то рецепты для каждого приема пищи
    for meal_type, recipes in pools.items():
        if not recipes:
            # Если для какого-то приема пищи нет рецептов, выводим ошибку
            # или возвращаем пустой план, чтобы избежать проблем
            print(f"Внимание: Не найдены рецепты для приема пищи '{meal_type}'.")
            # Можно вернуть пустой план или сообщение об ошибке,
            # чтобы пользователь знал, что фильтры слишком строгие.
            # Для отладки, можно временно вернуть все рецепты.
            # return [] # или какой-то индикатор ошибки

    for p in pools.values():
         rng.shuffle(p)
    iterators = {m: iter(p) for m, p in pools.items()}

    for day_name in days:
        day_meals = []
        for m_slug, details in meal_dist.items():
            try:
                recipe = next(iterators[m_slug])
            except (StopIteration, KeyError):
                if not pools.get(m_slug): continue
                rng.shuffle(pools[m_slug])
                iterators[m_slug] = iter(pools[m_slug])
                recipe = next(iterators[m_slug])
            
            multiplier = (target_kcal * details['ratio']) / recipe.calories if recipe.calories > 0 else 1
            day_meals.append({
                'id': recipe.id,
                'type': details['label'],
                'type_slug': m_slug,
                'title': recipe.title,
                'weight': round(100 * multiplier),
                'kcal': round(recipe.calories * multiplier),
                'p': round(recipe.protein * multiplier),
                'f': round(recipe.fat * multiplier),
                'c': round(recipe.carbs * multiplier),
                'image': recipe.image_url,
                'ingredients': scale_ingredients(recipe.description, multiplier),
            })
        weekly_plan.append({'day_name': day_name, 'meals': day_meals})

    return weekly_plan

def calculate_macros(data):
    """
    Универсальный расчет КБЖУ. 
    Принимает либо объект Profile, либо словарь сессии (для гостей).
    """
    
    # 1. Извлекаем данные в зависимости от типа входных данных
    if hasattr(data, 'weight'):
        # Если это объект Profile (доступ через точку)
        w = float(data.weight)
        h = float(data.height)
        a = int(data.age)
        g = data.gender
        activity = float(data.activity)
        goal = data.goal
    else:
        # Если это словарь сессии (доступ через .get())
        w = float(data.get('weight', 0))
        h = float(data.get('height', 0))
        a = int(data.get('age', 0))
        g = data.get('gender', 'male')
        activity = float(data.get('activity', 1.2))
        goal = data.get('goal', 'maintain')

    # 2. Расчет BMR по формуле Миффлина-Сан Жеора
    if g == 'male':
        bmr = (10 * w) + (6.25 * h) - (5 * a) + 5
    else:
        bmr = (10 * w) + (6.25 * h) - (5 * a) - 161
    
    # 3. Учет активности (TDEE)
    tdee = bmr * activity
    
    # 4. Учет цели 
    if goal == 'lose':
        tdee *= 0.85 # Дефицит 15%
    elif goal == 'gain':
        tdee *= 1.15 # Профицит 15%
        
    # 5. Расчет БЖУ 
    protein = (tdee * 0.30) / 4
    fat = (tdee * 0.30) / 9
    carbs = (tdee * 0.40) / 4
    
    return {
        'kcal': round(tdee),
        'p': round(protein),
        'f': round(fat),
        'c': round(carbs)
    }