
import datetime
import random
import re
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import login

from .models import Profile, Recipe
from .forms import RegisterForm
from .logic import calculate_macros

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def scale_ingredients(description, multiplier):
    """Пересчет граммовки ингредиентов."""
    if not description: return ""
    def replace(match):
        value = float(match.group(1))
        return f"{round(value * multiplier)}"
    return re.sub(r'(\d+(?:\.\d+)?)(?=\s*(?:г|мл|шт))', replace, description)

# --- ГЛАВНЫЕ СТРАНИЦЫ ---
def index(request):
    return render(request, 'core/index.html', {'hide_footer': False})

def menu_types(request):
    diet_categories = [
        {'slug': 'all', 'name': 'Всеядное', 'desc': 'Классический рацион без ограничений.'},
        {'slug': 'pesca', 'name': 'Пескетарианское', 'desc': 'Без мяса, но с рыбой и морепродуктами.'},
        {'slug': 'vege', 'name': 'Вегетарианское', 'desc': 'Только растительная пища + молоко и яйца.'},
        {'slug': 'vegan', 'name': 'Веганское', 'desc': 'Строго растительный рацион.'},
    ]
    for diet in diet_categories:
        samples = Recipe.objects.filter(diet_type=diet['slug'])
        if samples.exists():
            diet['samples'] = random.sample(list(samples), min(len(samples), 2))
    return render(request, 'core/menu_types.html', {'diets': diet_categories})

# --- АВТОРИЗАЦИЯ И ВЕРИФИКАЦИЯ ---

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.is_active = True  # Пользователь активен сразу после регистрации
            user.save()

            # Создаем или получаем профиль для пользователя
            profile, created = Profile.objects.get_or_create(user=user)
            profile.save() # Сохраняем профиль, если он был только что создан или изменен

            # --- Автоматический вход пользователя ---
            login(request, user) # Логиним пользователя сразу после успешной регистрации
            # --------------------------------------------------------------------

            messages.success(request, "Аккаунт успешно создан! Вы успешно вошли.")
            # Перенаправляем пользователя в его личный кабинет 
            return redirect('profile') # <-- перенаправляем на страницу 'profile'

        else:
            # Если форма невалидна, выводим ошибки
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Ошибка при регистрации: {error}")
            return render(request, 'core/register.html', {'form': form})
    else:
        form = RegisterForm()
    return render(request, 'core/register.html', {'form': form})

def verify_email(request):
    user_id = request.session.get('unverified_user_id')
    if not user_id:
        return redirect('user_login')

    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        code = request.POST.get('code')
        if code == user.profile.verification_code:
            user.is_active = True
            user.save()
            user.profile.is_verified = True
            user.profile.verification_code = None
            user.profile.save()
            auth_login(request, user)
            messages.success(request, "Почта подтверждена!")
            return redirect('profile')
        else:
            messages.error(request, "Неверный код.")
    
    return render(request, 'core/verify_email.html', {'user_email': user.email})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                request.session['unverified_user_id'] = user.id
                return redirect('verify_email')
            auth_login(request, user)
            return redirect('profile')
        else:
            messages.error(request, "Неверный логин или пароль")
    return render(request, 'core/login.html', {'form': AuthenticationForm()})

def user_logout(request):
    auth_logout(request)
    return redirect('index')

# --- АНКЕТА ---
def individual_menu(request):
    step = request.GET.get('step', '1')
    if request.method == 'POST':
        if step == '1':
            request.session['goal'] = request.POST.get('goal')
            request.session['activity'] = request.POST.get('activity')
            return redirect('/individual-menu/?step=2')
            
        elif step == '2':
            try:
                age, weight, height = request.POST.get('age'), request.POST.get('weight'), request.POST.get('height')
                gender = request.POST.get('gender')
                if not all([age, weight, height, gender]):
                    raise ValueError("Заполните все поля")
                
                errors = []
                age, weight, height = int(age), float(weight), float(height)
                if not (12 <= age <= 110): errors.append("Возраст от 12 до 110")
                if not (30 <= weight <= 300): errors.append("Вес от 30 до 300")
                if not (120 <= height <= 250): errors.append("Рост от 120 до 250")
                
                if errors:
                    return render(request, 'core/step_2.html', {'errors': errors, 'hide_footer': True})
                
                request.session.update({'age': age, 'weight': weight, 'height': height, 'gender': gender})
                return redirect('/individual-menu/?step=3')
            except ValueError:
                return render(request, 'core/step_2.html', {'errors': ["Введите корректные числа"], 'hide_footer': True})

        elif step == '3':
            request.session['diet_pref'] = request.POST.get('diet')
            request.session['allergies'] = ",".join(request.POST.getlist('allergies'))
            
            if request.user.is_authenticated:
                p = request.user.profile
                p.goal = request.session.get('goal')
                p.age = request.session.get('age')
                p.weight = request.session.get('weight')
                p.height = request.session.get('height')
                p.gender = request.session.get('gender')
                p.activity = float(request.session.get('activity', 1.2))
                p.diet_pref = request.session.get('diet_pref')
                p.allergies = request.session.get('allergies')
                res = calculate_macros(p)
                p.target_kcal, p.target_protein = res['kcal'], res['p']
                p.target_fat, p.target_carbs = res['f'], res['c']
                p.save()
            return redirect('results')
            
    return render(request, f'core/step_{step}.html', {'hide_footer': True})

# --- ГЕНЕРАЦИЯ РАЦИОНА ---
def results(request):
    is_guest = not request.user.is_authenticated
    favorite_recipe_ids = []
    can_refresh = False
    days_left = 0

    if not is_guest:
        profile = request.user.profile
        source = profile
        if not profile.target_kcal: return redirect('individual_menu')
        favorite_recipe_ids = list(profile.favorite_recipes.values_list('id', flat=True))
        can_refresh = profile.can_refresh_menu()
        days_left = profile.days_until_next_refresh()
        is_subscribed = profile.has_active_subscription
    else:
        source = request.session
        if not source.get('age'): return redirect('individual_menu')
        is_subscribed = False

    res_macros = calculate_macros(source)
    target_kcal = res_macros['kcal']

    # Фильтрация по диете и аллергиям
    diet_pref = source.diet_pref if not is_guest else source.get('diet_pref')
    allergies = source.allergies if not is_guest else source.get('allergies', '')
    
    diet_map = {'vegan': ['vegan'], 'vege': ['vegan', 'vege'], 'pesca': ['vegan', 'vege', 'pesca'], 'all': ['vegan', 'vege', 'pesca', 'all']}
    allowed = diet_map.get(diet_pref, ['all'])
    
    recipes_query = Recipe.objects.filter(diet_type__in=allowed)
    if allergies:
        for a in allergies.split(','):
            if a.strip():
                recipes_query = recipes_query.exclude(description__icontains=a.strip())
    
    all_recipes = list(recipes_query)
    if not all_recipes:
        return render(request, 'core/results.html', {'error_message': "Нет рецептов под ваши фильтры."})

    meal_dist = {
        'breakfast': {'ratio': 0.25, 'label': 'ЗАВТРАК'},
        'snack': {'ratio': 0.15, 'label': 'ПЕРЕКУС'},
        'lunch': {'ratio': 0.35, 'label': 'ОБЕД'},
        'dinner': {'ratio': 0.25, 'label': 'УЖИН'},
    }
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    weekly_plan = []
    
    user_seed = request.user.id if not is_guest else "guest"
    refresh_seed = int(profile.last_weekly_refresh.timestamp()) if not is_guest and profile.last_weekly_refresh else 0
    random.seed(f"{user_seed}-{datetime.date.today().isocalendar()[1]}-{refresh_seed}")

    pools = {m: [r for r in all_recipes if r.meal_type == m] for m in meal_dist.keys()}
    for p in pools.values(): random.shuffle(p)
    iterators = {m: iter(p) for m, p in pools.items()}

    for day_name in days:
        day_meals = []
        for m_slug, details in meal_dist.items():
            try:
                recipe = next(iterators[m_slug])
            except (StopIteration, KeyError):
                if not pools.get(m_slug): continue
                random.shuffle(pools[m_slug])
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

    return render(request, 'core/results.html', {
        'weekly_plan': weekly_plan,
        'macros': res_macros,
        'kcal': target_kcal,
        'is_guest': is_guest,
        'can_refresh': can_refresh,
        'days_left': days_left,
        'favorite_recipe_ids': favorite_recipe_ids,
        'is_subscribed': is_subscribed,
        'hide_footer': True
    })

# --- AJAX И ФИЧИ ---

@login_required
@require_POST
def toggle_favorite(request):
    data = json.loads(request.body)
    recipe = get_object_or_404(Recipe, id=data.get('recipe_id'))
    profile = request.user.profile
    if recipe in profile.favorite_recipes.all():
        profile.favorite_recipes.remove(recipe)
        return JsonResponse({'status': 'success', 'action': 'removed'})
    else:
        profile.favorite_recipes.add(recipe)
        return JsonResponse({'status': 'success', 'action': 'added'})

@login_required
def refresh_meal(request):
    profile = request.user.profile
    if profile.can_refresh_menu():
        profile.last_weekly_refresh = timezone.now()
        profile.save()
        messages.success(request, "Меню успешно обновлено на неделю!")
    else:
        messages.error(request, f"Бесплатное обновление будет доступно через {profile.days_until_next_refresh()} дн.")
    return redirect('results')

@login_required
@require_POST
def replace_meal_ajax(request):
    profile = request.user.profile
    if not profile.has_active_subscription:
        return JsonResponse({'status': 'error', 'message': 'Нужна подписка Premium'}, status=403)
    
    data = json.loads(request.body)
    meal_type = data.get('meal_type')
    old_id = data.get('recipe_id')
    
    recipes = Recipe.objects.filter(meal_type=meal_type, diet_type__in=[profile.diet_pref, 'all']).exclude(id=old_id)
    if not recipes.exists():
        return JsonResponse({'status': 'error', 'message': 'Нет вариантов для замены'}, status=404)
    
    new_recipe = random.choice(recipes)
    target_kcal = calculate_macros(profile)['kcal']
    meal_ratios = {'breakfast': 0.25, 'snack': 0.15, 'lunch': 0.35, 'dinner': 0.25}
    multiplier = (target_kcal * meal_ratios.get(meal_type, 0.25)) / new_recipe.calories
    
    return JsonResponse({
        'status': 'success',
        'new_meal': {
            'id': new_recipe.id,
            'title': new_recipe.title,
            'kcal': round(new_recipe.calories * multiplier),
            'p': round(new_recipe.protein * multiplier),
            'f': round(new_recipe.fat * multiplier),
            'c': round(new_recipe.carbs * multiplier),
            'weight': round(100 * multiplier),
            'ingredients': scale_ingredients(new_recipe.description, multiplier),
            'image': new_recipe.image_url
        }
    })

@login_required
def profile_view(request):
    user_profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, 'core/profile.html', {
        'profile': user_profile,
        'favorite_recipes': user_profile.favorite_recipes.all(),
        'days_left': user_profile.days_until_next_refresh()
    })
