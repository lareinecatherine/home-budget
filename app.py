from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"postgresql+psycopg://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# === МОДЕЛИ ===

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    icon = db.Column(db.String(50), default='bi-circle')
    
    transactions = db.relationship('Transaction', backref='category', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    comment = db.Column(db.Text)
    transaction_date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Budget(db.Model):
    __tablename__ = 'budgets'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer, 
        db.ForeignKey('categories.id', ondelete='CASCADE'),  # <-- Добавили ondelete='CASCADE'
        nullable=False
    )
    limit_amount = db.Column(db.Numeric(10, 2), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    
    category = db.relationship('Category', backref='budgets')

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def get_current_month_budgets(user_categories):
    now = datetime.now()
    budgets = Budget.query.filter(
        Budget.category_id.in_([c.id for c in user_categories]),
        Budget.month == now.month,
        Budget.year == now.year
    ).all()
    return {b.category_id: b for b in budgets}

def calculate_category_spent(category_id, month, year):
    result = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.category_id == category_id,
        Transaction.type == 'expense',
        func.extract('month', Transaction.transaction_date) == month,
        func.extract('year', Transaction.transaction_date) == year
    ).scalar()
    return float(result or 0)

def get_budget_status(spent, limit):
    if limit == 0:
        return 'none', 0, 'Без лимита'
    percent = (spent / limit) * 100
    if percent >= 100:
        return 'danger', min(percent, 100), f'Перерасход: +{percent-100:.0f}%'
    elif percent >= 80:
        return 'warning', percent, f'Внимание: {100-percent:.0f}% осталось до превышения лимита'
    else:
        return 'success', percent, f'Осталось: {limit-spent:.0f} ₽'

# === МАРШРУТЫ ===

@app.route('/')
def dashboard():
    today = date.today().isoformat()
    now = datetime.now()
    
    # === ПОЛУЧАЕМ ВЫБРАННЫЙ ПЕРИОД ===
    period = request.args.get('period', 'month')  # month, year, all
    selected_month = request.args.get('month', now.month, type=int)
    selected_year = request.args.get('year', now.year, type=int)
    
    # === ОПРЕДЕЛЯЕМ ДАТЫ ДЛЯ ФИЛЬТРАЦИИ ===
    if period == 'month':
        filter_month = selected_month
        filter_year = selected_year
        period_label = f"{get_month_name(filter_month)} {filter_year}"
    elif period == 'year':
        filter_month = None
        filter_year = selected_year
        period_label = f"{filter_year} год"
    else:  # all
        filter_month = None
        filter_year = None
        period_label = "За всё время"
    
    # === ПОЛУЧАЕМ ВСЕ ТРАНЗАКЦИИ (для таблицы) ===
    transactions = Transaction.query.order_by(Transaction.transaction_date.desc()).all()
    
    # === ФИЛЬТРУЕМ ТРАНЗАКЦИИ ДЛЯ СТАТИСТИКИ ===
    filtered_transactions = []
    for t in transactions:
        if period == 'month':
            if t.transaction_date.month == filter_month and t.transaction_date.year == filter_year:
                filtered_transactions.append(t)
        elif period == 'year':
            if t.transaction_date.year == filter_year:
                filtered_transactions.append(t)
        else:  # all
            filtered_transactions.append(t)
    
    # === ИТОГИ ЗА ВЫБРАННЫЙ ПЕРИОД ===
    income = sum(t.amount for t in filtered_transactions if t.type == 'income')
    expenses = sum(t.amount for t in filtered_transactions if t.type == 'expense')
    balance = income - expenses
    
    # === КАТЕГОРИИ ===
    categories = Category.query.all()
    expense_categories = [c for c in categories if c.type == 'expense']
    
    # === БЮДЖЕТЫ (только для периода "месяц") ===
    budgets = get_current_month_budgets(expense_categories) if period == 'month' else {}
    budget_statuses = []
    
    for cat in expense_categories:
        if period == 'month' and cat.id in budgets:
            budget = budgets[cat.id]
            spent = calculate_category_spent(cat.id, filter_month, filter_year)
            status, percent, message = get_budget_status(spent, float(budget.limit_amount))
            budget_statuses.append({
                'category': cat,
                'spent': spent,
                'limit': float(budget.limit_amount),
                'percent': percent,
                'status': status,
                'message': message
            })
    
    # === ДАННЫЕ ДЛЯ ДИАГРАММЫ ===
    CATEGORY_COLORS = {
        'Еда': '#dc3545',
        'Транспорт': '#0d6efd',
        'Развлечения': '#6f42c1',
        'Жильё': '#20c997',
        'Здоровье': '#fd7e14',
        'Подарки': '#e83e8c',
        'Зарплата': '#198754',
        'Другое': '#6c757d',
    }
    
    chart_labels = []
    chart_data = []
    chart_colors = []
    
    for cat in expense_categories:
        if period == 'month':
            spent = calculate_category_spent(cat.id, filter_month, filter_year)
        elif period == 'year':
            spent = calculate_category_spent_year(cat.id, filter_year)
        else:  # all
            spent = sum(t.amount for t in cat.transactions if t.type == 'expense')
        
        if spent > 0:
            chart_labels.append(cat.name)
            chart_data.append(float(spent))
            color = CATEGORY_COLORS.get(cat.name, f'hsl({hash(cat.name) % 360}, 70%, 50%)')
            chart_colors.append(color)
    
    # === УВЕДОМЛЕНИЯ ===
    alerts = [bs for bs in budget_statuses if bs['status'] in ['warning', 'danger']]
    
    return render_template('dashboard.html', 
                         transactions=transactions,
                         income=income,
                         expenses=expenses,
                         balance=balance,
                         categories=categories,
                         today=today,
                         budget_statuses=budget_statuses,
                         chart_labels=chart_labels,
                         chart_data=chart_data,
                         chart_colors=chart_colors,
                         alerts=alerts,
                         period=period,
                         selected_month=selected_month,
                         selected_year=selected_year,
                         period_label=period_label)

# === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ===
def get_month_name(month):
    months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
              'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    return months[month - 1]

def calculate_category_spent_year(category_id, year):
    """Считает потраченную сумму по категории за год"""
    result = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.category_id == category_id,
        Transaction.type == 'expense',
        func.extract('year', Transaction.transaction_date) == year
    ).scalar()
    return float(result or 0)
    
    # ПАЛИТРА ЦВЕТОВ ДЛЯ ДИАГРАММЫ
    CATEGORY_COLORS = {
        'Еда': '#dc3545',
        'Транспорт': '#0d6efd',
        'Развлечения': '#6f42c1',
        'Жильё': '#20c997',
        'Здоровье': '#fd7e14',
        'Подарки': '#e83e8c',
        'Зарплата': '#198754',
        'Другое': '#6c757d',
        'Кафе': '#fd7e14',
        'Такси': '#0dcaf0',
    }
    
    chart_labels = []
    chart_data = []
    chart_colors = []
    
    for cat in expense_categories:
        spent = calculate_category_spent(cat.id, now.month, now.year)
        if spent > 0:
            chart_labels.append(cat.name)
            chart_data.append(float(spent))
            color = CATEGORY_COLORS.get(cat.name, f'hsl({hash(cat.name) % 360}, 70%, 50%)')
            chart_colors.append(color)
    
    alerts = [bs for bs in budget_statuses if bs['status'] in ['warning', 'danger']]
    
    return render_template('dashboard.html', 
                         transactions=transactions,
                         income=income,
                         expenses=expenses,
                         balance=balance,
                         categories=categories,
                         today=today,
                         budget_statuses=budget_statuses,
                         chart_labels=chart_labels,
                         chart_data=chart_data,
                         chart_colors=chart_colors,
                         alerts=alerts)

@app.route('/add', methods=['POST'])
def add_transaction():
    try:
        amount = float(request.form['amount'])
        category_id = int(request.form['category'])
        t_type = request.form['type']
        comment = request.form.get('comment', '')
        t_date = request.form.get('date')
        
        transaction_date = datetime.strptime(t_date, '%Y-%m-%d').date() if t_date else date.today()
        
        # === ПРОВЕРКА ЛИМИТА ТОЛЬКО ДЛЯ ТЕКУЩЕГО МЕСЯЦА ===
        now = datetime.now()
        
        if t_type == 'expense':
            # Проверяем, является ли транзакция текущим месяцем
            is_current_month = (
                transaction_date.month == now.month and 
                transaction_date.year == now.year
            )
            
            if is_current_month:
                category = Category.query.get(category_id)
                budget = Budget.query.filter_by(
                    category_id=category_id,
                    month=now.month,
                    year=now.year
                ).first()
                
                if budget:
                    spent = calculate_category_spent(category_id, now.month, now.year)
                    if spent + amount > float(budget.limit_amount):
                        flash(f'⚠️ Внимание: Превышен лимит категории "{category.name}"!', 'warning')
        
        new_transaction = Transaction(
            amount=amount,
            category_id=category_id,
            type=t_type,
            comment=comment,
            transaction_date=transaction_date
        )
        
        db.session.add(new_transaction)
        db.session.commit()
        flash('✅ Транзакция добавлена!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:id>')
def delete_transaction(id):
    try:
        transaction = Transaction.query.get_or_404(id)
        db.session.delete(transaction)
        db.session.commit()
        flash('🗑️ Транзакция удалена', 'info')
    except:
        db.session.rollback()
        flash('❌ Ошибка при удалении', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/set-budget', methods=['POST'])
def set_budget():
    try:
        category_id = int(request.form['category_id'])
        limit = float(request.form['limit'])
        now = datetime.now()
        
        budget = Budget.query.filter_by(
            category_id=category_id,
            month=now.month,
            year=now.year
        ).first()
        
        if budget:
            budget.limit_amount = limit
        else:
            new_budget = Budget(
                category_id=category_id,
                limit_amount=limit,
                month=now.month,
                year=now.year
            )
            db.session.add(new_budget)
        
        db.session.commit()
        flash('💰 Бюджет установлен!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/add-category', methods=['POST'])
def add_category():
    try:
        name = request.form['name'].strip()
        t_type = request.form['type']
        
        # Автоматически назначаем иконку по умолчанию
        icon = 'bi-circle'
        
        if not name:
            flash('❌ Название категории не может быть пустым', 'danger')
            return redirect(url_for('dashboard'))
        
        exists = Category.query.filter_by(name=name, type=t_type).first()
        if exists:
            flash(f'⚠️ Категория "{name}" уже существует', 'warning')
            return redirect(url_for('dashboard'))
        
        new_category = Category(name=name, type=t_type, icon=icon)
        db.session.add(new_category)
        db.session.commit()
        
        flash(f'✅ Категория "{name}" добавлена!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/delete-category/<int:id>')
def delete_category(id):
    try:
        category = Category.query.get_or_404(id)
        
        # 1. Проверяем транзакции — если есть, блокируем удаление
        transactions_count = Transaction.query.filter_by(category_id=category.id).count()
        if transactions_count > 0:
            flash(f'⚠️ Нельзя удалить "{category.name}": есть {transactions_count} транзакций', 'warning')
            return redirect(url_for('dashboard'))
        
        # 2. ✅ УДАЛЯЕМ БЮДЖЕТЫ ЧЕРЕЗ RAW SQL (обходим проблемы ORM)
        from sqlalchemy import text
        db.session.execute(
            text("DELETE FROM budgets WHERE category_id = :cat_id"),
            {"cat_id": category.id}
        )
        db.session.flush()  # Немедленно выполняем SQL
        
        # 3. Теперь удаляем саму категорию
        db.session.delete(category)
        db.session.commit()
        
        flash(f'🗑️ Категория "{category.name}" удалена', 'info')
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Ошибка удаления категории: {e}")
        flash(f'❌ Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/test-db')
def test_db():
    try:
        count = Category.query.count()
        return f"<h1>✅ Подключение успешно!</h1><p>База: {os.getenv('DB_NAME')}</p><p>Категорий: {count}</p><a href='/'>На главную</a>"
    except Exception as e:
        return f"<h1>❌ Ошибка:</h1><p>{e}</p><a href='/'>Назад</a>"

# === ЗАПУСК ===

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if Category.query.count() == 0:
            cats = [
                Category(name='Зарплата', type='income', icon='bi-cash-coin'),
                Category(name='Еда', type='expense', icon='bi-cart'),
                Category(name='Транспорт', type='expense', icon='bi-bus-front'),
                Category(name='Развлечения', type='expense', icon='bi-film'),
                Category(name='Жильё', type='expense', icon='bi-house'),
                Category(name='Здоровье', type='expense', icon='bi-heart-pulse'),
                Category(name='Подарки', type='expense', icon='bi-gift'),
                Category(name='Другое', type='expense', icon='bi-three-dots'),
            ]
            db.session.add_all(cats)
            db.session.commit()
            print("Категории добавлены!")
    app.run(debug=True)