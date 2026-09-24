import json
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.finance import Income, Expense, BudgetGoal, ALLOWED_CATEGORIES
from app.services.ai_service import get_quick_insight

dashboard_bp = Blueprint('dashboard', __name__)


def calculate_user_monthly_financials(user_id: int, target_date: date = None) -> dict:
    """Calculate all monthly KPIs, category breakdowns, and recent transactions."""
    if target_date is None:
        target_date = date.today()

    start_of_month = date(target_date.year, target_date.month, 1)
    if target_date.month == 12:
        start_of_next_month = date(target_date.year + 1, 1, 1)
    else:
        start_of_next_month = date(target_date.year, target_date.month + 1, 1)

    # Monthly scoped queries
    incomes = Income.query.filter(
        Income.user_id == user_id,
        Income.date >= start_of_month,
        Income.date < start_of_next_month
    ).all()

    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= start_of_month,
        Expense.date < start_of_next_month
    ).all()

    monthly_income = float(sum(inc.amount for inc in incomes))
    monthly_expenses = float(sum(exp.amount for exp in expenses))
    net_balance = monthly_income - monthly_expenses

    # Prevent division by zero
    if monthly_income > 0:
        savings_rate = ((monthly_income - monthly_expenses) / monthly_income) * 100.0
    else:
        savings_rate = 0.0

    # Category totals
    category_totals = {cat: 0.0 for cat in ALLOWED_CATEGORIES}
    for exp in expenses:
        if exp.category in category_totals:
            category_totals[exp.category] += float(exp.amount)
        else:
            category_totals['Other'] = category_totals.get('Other', 0.0) + float(exp.amount)

    # Budget goals
    budget_goal = BudgetGoal.query.filter_by(user_id=user_id).first()
    monthly_budget = float(budget_goal.monthly_limit) if budget_goal else 0.0
    target_savings_rate = float(budget_goal.target_savings_rate) if budget_goal else 20.0

    if monthly_budget > 0:
        budget_utilization = (monthly_expenses / monthly_budget) * 100.0
    else:
        budget_utilization = 0.0

    # Recent 10 combined transactions
    user_incomes = Income.query.filter_by(user_id=user_id).order_by(Income.date.desc(), Income.id.desc()).limit(15).all()
    user_expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc(), Expense.id.desc()).limit(15).all()

    combined = []
    for inc in user_incomes:
        combined.append({
            'id': inc.id,
            'type': 'income',
            'description': inc.source,
            'category_or_source': inc.source,
            'amount': float(inc.amount),
            'date': inc.date.isoformat(),
            'sort_key': (inc.date, inc.id)
        })

    for exp in user_expenses:
        combined.append({
            'id': exp.id,
            'type': 'expense',
            'description': exp.title,
            'category_or_source': exp.category,
            'amount': float(exp.amount),
            'date': exp.date.isoformat(),
            'sort_key': (exp.date, exp.id)
        })

    combined.sort(key=lambda x: x['sort_key'], reverse=True)
    recent_transactions = combined[:10]

    return {
        'month_name': target_date.strftime('%B'),
        'year': target_date.year,
        'monthly_income': monthly_income,
        'monthly_expenses': monthly_expenses,
        'net_balance': net_balance,
        'savings_rate': savings_rate,
        'category_totals': category_totals,
        'monthly_budget': monthly_budget,
        'budget_utilization': budget_utilization,
        'target_savings_rate': target_savings_rate,
        'recent_transactions': recent_transactions,
        'has_budget': budget_goal is not None
    }


@dashboard_bp.route('/')
def index():
    """Root landing page redirecting to dashboard or login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))
    return redirect(url_for('auth.login'))


@dashboard_bp.route('/dashboard')
@login_required
def dashboard_view():
    """Main dashboard displaying monthly KPIs, charts, and budget progress."""
    data = calculate_user_monthly_financials(current_user.id)
    quick_insight = get_quick_insight(data)

    chart_labels = list(data['category_totals'].keys())
    chart_values = [data['category_totals'][cat] for cat in chart_labels]

    return render_template(
        'dashboard.html',
        data=data,
        quick_insight=quick_insight,
        chart_labels_json=json.dumps(chart_labels),
        chart_values_json=json.dumps(chart_values),
        today_date=date.today().isoformat()
    )


@dashboard_bp.route('/tracker')
@login_required
def tracker_view():
    """Transaction management page with income, expense, and budget forms."""
    user_incomes = Income.query.filter_by(user_id=current_user.id).order_by(Income.date.desc(), Income.id.desc()).all()
    user_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc(), Expense.id.desc()).all()
    budget_goal = BudgetGoal.query.filter_by(user_id=current_user.id).first()

    return render_template(
        'tracker.html',
        incomes=user_incomes,
        expenses=user_expenses,
        budget_goal=budget_goal,
        allowed_categories=ALLOWED_CATEGORIES,
        today_date=date.today().isoformat()
    )


@dashboard_bp.route('/add-income', methods=['POST'])
@login_required
def add_income():
    """Add a new income entry for current user."""
    source = request.form.get('source', '').strip()
    amount_raw = request.form.get('amount', '').strip()
    date_raw = request.form.get('date', '').strip()

    if not source:
        flash("Income source cannot be empty.", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        amount = float(amount_raw)
        if amount <= 0 or amount != amount:  # Check for NaN / negative
            raise ValueError()
    except (ValueError, TypeError):
        flash("Income amount must be a positive number.", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        tx_date = datetime.strptime(date_raw, '%Y-%m-%d').date() if date_raw else date.today()
    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        income = Income(
            user_id=current_user.id,
            source=source,
            amount=round(amount, 2),
            date=tx_date
        )
        income.validate()
        db.session.add(income)
        db.session.commit()
        flash(f"Income of ₹{amount:,.2f} from '{source}' added successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to record income: {str(e)}", "danger")

    return redirect(url_for('dashboard.tracker_view'))


@dashboard_bp.route('/delete-income/<int:id>', methods=['POST'])
@login_required
def delete_income(id: int):
    """Delete an income entry, strictly verifying user ownership."""
    income = Income.query.filter_by(id=id, user_id=current_user.id).first()

    if not income:
        flash("Unauthorized or transaction not found.", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        db.session.delete(income)
        db.session.commit()
        flash("Income record deleted successfully.", "info")
    except Exception:
        db.session.rollback()
        flash("Failed to delete income record. Please try again.", "danger")

    return redirect(url_for('dashboard.tracker_view'))


@dashboard_bp.route('/add-expense', methods=['POST'])
@login_required
def add_expense():
    """Add a new expense entry for current user."""
    title = request.form.get('title', '').strip()
    amount_raw = request.form.get('amount', '').strip()
    category = request.form.get('category', '').strip()
    date_raw = request.form.get('date', '').strip()

    if not title:
        flash("Expense title cannot be empty.", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        amount = float(amount_raw)
        if amount <= 0 or amount != amount:  # Check for NaN / negative
            raise ValueError()
    except (ValueError, TypeError):
        flash("Expense amount must be a positive number.", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    if category not in ALLOWED_CATEGORIES:
        flash(f"Invalid category selected. Choose from: {', '.join(ALLOWED_CATEGORIES)}", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        tx_date = datetime.strptime(date_raw, '%Y-%m-%d').date() if date_raw else date.today()
    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        expense = Expense(
            user_id=current_user.id,
            title=title,
            amount=round(amount, 2),
            category=category,
            date=tx_date
        )
        expense.validate()
        db.session.add(expense)
        db.session.commit()
        flash(f"Expense of ₹{amount:,.2f} for '{title}' recorded!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to record expense: {str(e)}", "danger")

    return redirect(url_for('dashboard.tracker_view'))


@dashboard_bp.route('/delete-expense/<int:id>', methods=['POST'])
@login_required
def delete_expense(id: int):
    """Delete an expense entry, strictly verifying user ownership."""
    expense = Expense.query.filter_by(id=id, user_id=current_user.id).first()

    if not expense:
        flash("Unauthorized or transaction not found.", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        db.session.delete(expense)
        db.session.commit()
        flash("Expense record deleted successfully.", "info")
    except Exception:
        db.session.rollback()
        flash("Failed to delete expense record. Please try again.", "danger")

    return redirect(url_for('dashboard.tracker_view'))


@dashboard_bp.route('/set-budget', methods=['POST'])
@login_required
def set_budget():
    """Set or update the user's monthly budget limit and savings rate target."""
    limit_raw = request.form.get('monthly_limit', '').strip()
    rate_raw = request.form.get('target_savings_rate', '').strip()

    try:
        monthly_limit = float(limit_raw)
        if monthly_limit < 0 or monthly_limit != monthly_limit:
            raise ValueError("Budget limit cannot be negative.")
    except (ValueError, TypeError):
        flash("Please enter a valid numeric budget limit (>= 0).", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        target_savings_rate = float(rate_raw)
        if not (0 <= target_savings_rate <= 100) or target_savings_rate != target_savings_rate:
            raise ValueError("Target savings rate must be between 0% and 100%.")
    except (ValueError, TypeError):
        flash("Please enter a valid savings rate between 0 and 100%.", "danger")
        return redirect(url_for('dashboard.tracker_view'))

    try:
        goal = BudgetGoal.query.filter_by(user_id=current_user.id).first()
        if not goal:
            goal = BudgetGoal(
                user_id=current_user.id,
                monthly_limit=round(monthly_limit, 2),
                target_savings_rate=round(target_savings_rate, 1)
            )
            db.session.add(goal)
        else:
            goal.monthly_limit = round(monthly_limit, 2)
            goal.target_savings_rate = round(target_savings_rate, 1)

        goal.validate()
        db.session.commit()
        flash("Monthly budget goal and savings targets saved!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to save budget settings: {str(e)}", "danger")

    return redirect(url_for('dashboard.tracker_view'))
