
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
from django.db.models import Sum, Q 
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from .models import Profile, Recipe
from .forms import RegisterForm
from .logic import calculate_macros, scale_ingredients, generate_weekly_plan

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

# --- АВТОРИЗАЦИЯ И ВЕРИФИКАЦИЯ (ИСПРАВЛЕНО) ---

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            # 1. Проверка достоверности формата почты
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, "Введите корректный адрес почты (например, name@mail.ru)")
                return render(request, 'core/register.html', {'form': form})

            # 2. Проверка уникальности почты 
            if User.objects.filter(email=email).exists():
                messages.error(request, "Эта почта уже занята другим аккаунтом.")
                return render(request, 'core/register.html', {'form': form})

            # 3. Создание пользователя
            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()

            # Профиль создается автоматически сигналом 
            login(request, user)
            messages.success(request, "Аккаунт успешно создан! Добро пожаловать.")
            return redirect('profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
            return render(request, 'core/register.html', {'form': form})
    else:
        form = RegisterForm()
    return render(request, 'core/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect('profile')
        else:
            # Вывод ошибки при неправильном пароле
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
                age = request.POST.get('age')
                weight = request.POST.get('weight')
                height = request.POST.get('height')
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
            
            # Принудительно сохраняем сессию, чтобы данные не пропали
            request.session.modified = True

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

# --- ГЕНЕРАЦИЯ РАЦИОНА (ИСПРАВЛЕНО: АЛЛЕРГИИ) ---

def results(request):
    is_guest = not request.user.is_authenticated
    favorite_recipe_ids = []
    can_refresh = False
    days_left = 0
    is_subscribed = False

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

    res_macros = calculate_macros(source)
    target_kcal = res_macros['kcal']

    # 1. Получаем рецепты, отфильтрованные только по диете из БД
    diet_pref = source.diet_pref if not is_guest else source.get('diet_pref', 'all')
    diet_map = {
        'vegan': ['vegan'],
        'vege': ['vegan', 'vege'],
        'pesca': ['vegan', 'vege', 'pesca'],
        'all': ['vegan', 'vege', 'pesca', 'all']
    }
    allowed = diet_map.get(diet_pref, ['all'])
    
    # Сначала запрашиваем все рецепты, подходящие по диете
    recipes_from_db = Recipe.objects.filter(diet_type__in=allowed).order_by('id')
    
    # Превращаем в список Python для надежной фильтрации кириллицы
    all_recipes = list(recipes_from_db)

    # 2. УМНЫЙ ФИЛЬТР АЛЛЕРГИЙ НА УРОВНЕ PYTHON 
    allergies_str = source.allergies if not is_guest else source.get('allergies', '')
    
    if allergies_str:
        # Карта аллергий (ключи должны совпадать с 'value' из HTML, стоп-слова - в нижнем регистре)
        allergy_map = {
            'лактоз': ['молоко', 'творог', 'кефир', 'йогурт', 'сметан', 'сыр', 'рикотт', 'сливк', 'масло', 'молочный'],
            'глютен': ['пшенич', 'хлеб', 'мука', 'овсян', 'булгур', 'кускус', 'ячмень'],
            'орех': ['орех', 'миндаль', 'арахис', 'фундук', 'кешью'],
            'морепродукт': ['креветк', 'рыба', 'лосось', 'тунец', 'миди', 'кальмар', 'осьминог', 'икра']
        }
        
        selected_allergies = [a.strip().lower() for a in allergies_str.split(',') if a.strip()]
        
        filtered_recipes = []
        for recipe in all_recipes:
            keep_recipe = True
            # Текст, в котором ищем (название + описание) в нижнем регистре
            search_text = (recipe.title + " " + recipe.description).lower()
            
            for allergy_key in selected_allergies: # Теперь allergy_key будет 'лактоз', 'орех' и т.д.
                # Если это стандартная аллергия из карты
                if allergy_key in allergy_map:
                    stop_words = allergy_map[allergy_key]
                    if any(word in search_text for word in stop_words):
                        keep_recipe = False
                        break # Если нашли стоп-слово, этот рецепт не подходит
                # Если аллергия введена вручную и это слово есть в тексте
                elif allergy_key in search_text: # Этот блок сработает для любой произвольной строчки, не из карты
                    keep_recipe = False
                    break
            
            if keep_recipe:
                filtered_recipes.append(recipe)
        
        all_recipes = filtered_recipes # Обновляем список рецептов на отфильтрованный

    if not all_recipes:
        return render(request, 'core/results.html', {'error_message': "Нет рецептов под ваши фильтры."})

    weekly_plan = generate_weekly_plan(source, all_recipes, target_kcal, is_guest=is_guest)
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

    # 1. Получаем все рецепты этого типа и диеты из БД
    diet_map = {
        'vegan': ['vegan'], 
        'vege': ['vegan', 'vege'], 
        'pesca': ['vegan', 'vege', 'pesca'], 
        'all': ['vegan', 'vege', 'pesca', 'all']
    }
    allowed = diet_map.get(profile.diet_pref, ['all'])
    
    recipes_list = list(Recipe.objects.filter(meal_type=meal_type, diet_type__in=allowed).exclude(id=old_id))

    # 2. Фильтруем аллергии на уровне Python (для надежной работы с кириллицей)
    if profile.allergies:
        allergy_map = {
            'лактоз': ['молоко', 'творог', 'кефир', 'йогурт', 'сметан', 'сыр', 'рикотт', 'сливк', 'масло', 'молочный'],
            'глютен': ['пшенич', 'хлеб', 'мука', 'овсян', 'булгур', 'кускус', 'ячмень'],
            'орех': ['орех', 'миндаль', 'арахис', 'фундук', 'кешью'],
            'морепродукт': ['креветк', 'рыба', 'лосось', 'тунец', 'миди', 'кальмар', 'осьминог', 'икра']
        }
        selected = [a.strip().lower() for a in profile.allergies.split(',') if a.strip()]
        
        valid_recipes = []
        for r in recipes_list:
            search_text = (r.title + " " + r.description).lower()
            forbidden = False
            for alg_key in selected:
                if alg_key in allergy_map:
                    if any(word in search_text for word in allergy_map[alg_key]):
                        forbidden = True; break
                elif alg_key in search_text:
                    forbidden = True; break
            if not forbidden:
                valid_recipes.append(r)
        recipes_list = valid_recipes # Обновляем список рецептов на отфильтрованный

    if not recipes_list:
        return JsonResponse({'status': 'error', 'message': 'Нет вариантов для замены'}, status=404)
            
    new_recipe = random.choice(recipes_list)
    target_kcal = calculate_macros(profile)['kcal']
    meal_ratios = {'breakfast': 0.25, 'snack': 0.15, 'lunch': 0.35, 'dinner': 0.25}
    multiplier = (target_kcal * meal_ratios.get(meal_type, 0.25)) / new_recipe.calories if new_recipe.calories > 0 else 1

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
