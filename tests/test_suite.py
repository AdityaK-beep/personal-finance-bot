import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

# Ensure application package is in sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from app import create_app, db
from app.models.user import User
from app.models.finance import Income, Expense, BudgetGoal, ALLOWED_CATEGORIES
from app.routes.dashboard import calculate_user_monthly_financials
from app.services.ai_service import AIService, build_financial_prompt, generate_local_fallback
from config import TestConfig


class PersonalFinanceMasterTestSuite(unittest.TestCase):
    """Autonomous Master Test Suite for Personal Finance Advisor Bot."""

    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # =========================================================================
    # 1. MODEL & RELATIONSHIP TESTS
    # =========================================================================
    def test_user_password_hashing(self):
        """Verify secure password hashing and verification."""
        user = User(username="testuser", email="test@example.com")
        user.set_password("SuperSecret123")
        self.assertNotEqual(user.password_hash, "SuperSecret123")
        self.assertTrue(user.check_password("SuperSecret123"))
        self.assertFalse(user.check_password("WrongPassword"))

        # Password minimum length validation
        with self.assertRaises(ValueError):
            user.set_password("123")

    def test_model_relationships_and_cascades(self):
        """Verify User 1-to-many Incomes, Expenses, and 1-to-1 BudgetGoal with orphan removal."""
        user = User(username="owner", email="owner@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        income = Income(user_id=user.id, source="Salary", amount=50000.0, date=date.today())
        expense = Expense(user_id=user.id, title="Rent", amount=15000.0, category="Rent", date=date.today())
        budget = BudgetGoal(user_id=user.id, monthly_limit=30000.0, target_savings_rate=25.0)

        db.session.add_all([income, expense, budget])
        db.session.commit()

        self.assertEqual(len(user.incomes), 1)
        self.assertEqual(len(user.expenses), 1)
        self.assertIsNotNone(user.budget_goal)
        self.assertEqual(user.budget_goal.monthly_limit, 30000.0)

        # Deleting user must cascade-delete all related transactions and budget
        db.session.delete(user)
        db.session.commit()

        self.assertEqual(Income.query.count(), 0)
        self.assertEqual(Expense.query.count(), 0)
        self.assertEqual(BudgetGoal.query.count(), 0)

    def test_expense_category_and_amount_validation(self):
        """Reject invalid expense categories and non-positive amounts."""
        user = User(username="validator", email="val@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        # Invalid category
        exp_invalid_cat = Expense(user_id=user.id, title="Test", amount=100.0, category="Cryptocurrency", date=date.today())
        with self.assertRaises(ValueError):
            exp_invalid_cat.validate()

        # Zero amount
        exp_zero = Expense(user_id=user.id, title="Test", amount=0.0, category="Groceries", date=date.today())
        with self.assertRaises(ValueError):
            exp_zero.validate()

        # Negative amount
        exp_neg = Expense(user_id=user.id, title="Test", amount=-50.0, category="Groceries", date=date.today())
        with self.assertRaises(ValueError):
            exp_neg.validate()

        # Valid expense
        exp_valid = Expense(user_id=user.id, title="Valid", amount=120.0, category="Groceries", date=date.today())
        exp_valid.validate()  # Should not raise

    # =========================================================================
    # 2. AUTHENTICATION & AUTHORIZATION TESTS
    # =========================================================================
    def test_registration_and_login_flow(self):
        """Test user registration, duplicate detection, and login credential checks."""
        # 1. Register User
        res = self.client.post('/register', data={
            'username': 'Alice',
            'email': 'alice@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome to your Personal Finance Advisor", res.data)

        # Logout before testing unauthenticated registration flows
        self.client.get('/logout', follow_redirects=True)

        # 2. Duplicate email registration
        res_dup = self.client.post('/register', data={
            'username': 'Alice2',
            'email': 'alice@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b"already exists", res_dup.data)

        # 3. Logout
        self.client.get('/logout', follow_redirects=True)

        # 4. Wrong password login
        res_wrong = self.client.post('/login', data={
            'email': 'alice@example.com',
            'password': 'WrongPassword!'
        }, follow_redirects=True)
        self.assertIn(b"Invalid email or password", res_wrong.data)

        # 5. Successful login
        res_ok = self.client.post('/login', data={
            'email': 'alice@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b"Welcome back, Alice!", res_ok.data)

    def test_unauthenticated_route_protection(self):
        """Ensure all financial endpoints redirect unauthenticated users to login."""
        protected_routes = [
            '/dashboard',
            '/tracker',
            '/ai-insights'
        ]
        for route in protected_routes:
            res = self.client.get(route, follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/login', res.headers['Location'])

    def test_cross_user_data_isolation_and_ownership(self):
        """MANDATORY CHECK: User A cannot mutate or delete User B's transactions."""
        # Create User A
        user_a = User(username="UserA", email="a@example.com")
        user_a.set_password("password123")
        # Create User B
        user_b = User(username="UserB", email="b@example.com")
        user_b.set_password("password123")
        db.session.add_all([user_a, user_b])
        db.session.commit()

        # Create transactions for User B
        inc_b = Income(user_id=user_b.id, source="Secret Bonus", amount=10000.0, date=date.today())
        exp_b = Expense(user_id=user_b.id, title="Private Doctor", amount=2500.0, category="Other", date=date.today())
        db.session.add_all([inc_b, exp_b])
        db.session.commit()
        inc_b_id = inc_b.id
        exp_b_id = exp_b.id

        # Log in as User A
        self.client.post('/login', data={'email': 'a@example.com', 'password': 'password123'})

        # User A attempts to delete User B's income
        res_del_inc = self.client.post(f'/delete-income/{inc_b_id}', follow_redirects=True)
        self.assertIn(b"Unauthorized or transaction not found", res_del_inc.data)

        # User A attempts to delete User B's expense
        res_del_exp = self.client.post(f'/delete-expense/{exp_b_id}', follow_redirects=True)
        self.assertIn(b"Unauthorized or transaction not found", res_del_exp.data)

        # Verify User B's records are untouched in database
        self.assertIsNotNone(db.session.get(Income, inc_b_id))
        self.assertIsNotNone(db.session.get(Expense, exp_b_id))

    # =========================================================================
    # 3. FINANCIAL CALCULATIONS & MONTH BOUNDARY TESTS
    # =========================================================================
    def test_monthly_boundary_correctness(self):
        """Ensure date filtering strictly isolates the current calendar month and year."""
        user = User(username="FinUser", email="fin@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        today = date.today()
        # Dates:
        current_tx_date = today
        prev_month_date = (today.replace(day=1) - timedelta(days=1))
        prev_year_date = today.replace(year=today.year - 1)
        next_month_date = (today.replace(day=28) + timedelta(days=10)).replace(day=1)

        # Add records across different periods
        inc_curr = Income(user_id=user.id, source="Current Salary", amount=50000.0, date=current_tx_date)
        inc_prev_m = Income(user_id=user.id, source="Old Month Salary", amount=40000.0, date=prev_month_date)
        inc_prev_y = Income(user_id=user.id, source="Old Year Salary", amount=30000.0, date=prev_year_date)
        inc_next_m = Income(user_id=user.id, source="Next Month Advance", amount=20000.0, date=next_month_date)

        exp_curr = Expense(user_id=user.id, title="Current Rent", amount=15000.0, category="Rent", date=current_tx_date)
        exp_prev_m = Expense(user_id=user.id, title="Old Month Rent", amount=15000.0, category="Rent", date=prev_month_date)
        exp_prev_y = Expense(user_id=user.id, title="Old Year Rent", amount=12000.0, category="Rent", date=prev_year_date)

        db.session.add_all([inc_curr, inc_prev_m, inc_prev_y, inc_next_m, exp_curr, exp_prev_m, exp_prev_y])
        db.session.commit()

        # Calculate current month financials
        fin = calculate_user_monthly_financials(user.id, target_date=today)

        # Only current month income (50,000) and current month expense (15,000) must be counted
        self.assertEqual(fin['monthly_income'], 50000.0)
        self.assertEqual(fin['monthly_expenses'], 15000.0)
        self.assertEqual(fin['net_balance'], 35000.0)
        self.assertAlmostEqual(fin['savings_rate'], 70.0)

    def test_benchmark_financial_test_matrix(self):
        """Test benchmark calculation: Income=50000, Expenses=28000 -> Balance=22000, Savings=44%."""
        user = User(username="Benchmark", email="bench@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        today = date.today()
        db.session.add(Income(user_id=user.id, source="Salary", amount=50000.0, date=today))
        db.session.add_all([
            Expense(user_id=user.id, title="Rent", amount=15000.0, category="Rent", date=today),
            Expense(user_id=user.id, title="Groceries", amount=5000.0, category="Groceries", date=today),
            Expense(user_id=user.id, title="Transport", amount=3000.0, category="Transport", date=today),
            Expense(user_id=user.id, title="Entertainment", amount=2000.0, category="Entertainment", date=today),
            Expense(user_id=user.id, title="Utilities", amount=2000.0, category="Utilities", date=today),
            Expense(user_id=user.id, title="Other", amount=1000.0, category="Other", date=today),
        ])
        db.session.commit()

        fin = calculate_user_monthly_financials(user.id, target_date=today)
        self.assertEqual(fin['monthly_income'], 50000.0)
        self.assertEqual(fin['monthly_expenses'], 28000.0)
        self.assertEqual(fin['net_balance'], 22000.0)
        self.assertAlmostEqual(fin['savings_rate'], 44.0)

    def test_zero_division_guard(self):
        """Ensure zero income, zero expenses, and zero budget handle safely without ZeroDivisionError."""
        user = User(username="ZeroUser", email="zero@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        fin = calculate_user_monthly_financials(user.id)
        self.assertEqual(fin['monthly_income'], 0.0)
        self.assertEqual(fin['monthly_expenses'], 0.0)
        self.assertEqual(fin['net_balance'], 0.0)
        self.assertEqual(fin['savings_rate'], 0.0)
        self.assertEqual(fin['budget_utilization'], 0.0)

    # =========================================================================
    # 4. CRUD OPERATIONS
    # =========================================================================
    def test_crud_endpoints(self):
        """Test Income, Expense, and Budget CRUD via HTTP requests."""
        # Register and login
        self.client.post('/register', data={
            'username': 'CrudUser',
            'email': 'crud@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })

        # Add Income
        res_inc = self.client.post('/add-income', data={
            'source': 'Consulting',
            'amount': '12500.50',
            'date': date.today().isoformat()
        }, follow_redirects=True)
        self.assertIn(b"Consulting", res_inc.data)

        # Add Expense
        res_exp = self.client.post('/add-expense', data={
            'title': 'High Speed Internet',
            'amount': '1299.00',
            'category': 'Utilities',
            'date': date.today().isoformat()
        }, follow_redirects=True)
        self.assertIn(b"High Speed Internet", res_exp.data)

        # Set Budget
        res_bgt = self.client.post('/set-budget', data={
            'monthly_limit': '25000.00',
            'target_savings_rate': '30.0'
        }, follow_redirects=True)
        self.assertIn(b"Monthly budget goal and savings targets saved", res_bgt.data)

        # Verify DB records
        user = User.query.filter_by(email='crud@example.com').first()
        inc = Income.query.filter_by(user_id=user.id).first()
        exp = Expense.query.filter_by(user_id=user.id).first()
        bgt = BudgetGoal.query.filter_by(user_id=user.id).first()
        self.assertEqual(inc.amount, 12500.50)
        self.assertEqual(exp.amount, 1299.00)
        self.assertEqual(bgt.monthly_limit, 25000.00)
        self.assertEqual(bgt.target_savings_rate, 30.0)

        # Delete Income
        self.client.post(f'/delete-income/{inc.id}', follow_redirects=True)
        self.assertIsNone(db.session.get(Income, inc.id))

        # Delete Expense
        self.client.post(f'/delete-expense/{exp.id}', follow_redirects=True)
        self.assertIsNone(db.session.get(Expense, exp.id))

    # =========================================================================
    # 5. AI SERVICE & GEMINI INTEGRATION TESTS
    # =========================================================================
    def test_ai_fallback_when_no_api_key(self):
        """AI Service must return local fallback gracefully when no API key is provided."""
        ai_service = AIService(api_key="")
        fin_data = {
            'monthly_income': 60000.0,
            'monthly_expenses': 30000.0,
            'net_balance': 30000.0,
            'savings_rate': 50.0,
            'monthly_budget': 35000.0,
            'budget_utilization': 85.7,
            'target_savings_rate': 20.0,
            'category_totals': {'Rent': 15000.0, 'Groceries': 8000.0, 'Utilities': 7000.0}
        }
        res = ai_service.generate_financial_advice(fin_data)
        self.assertFalse(res['success'])
        self.assertEqual(res['source'], 'fallback')
        self.assertIn("1. Financial Snapshot", res['content'])
        self.assertIn("50/30/20 Comparison", res['content'])

    def test_ai_service_with_mock_gemini_client(self):
        """AI Service with mock client generates expected response structure."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "## 1. Financial Snapshot\n* Monthly Income: ₹50,000\n## 2. Overspending Detection\n* Stable."
        mock_client.models.generate_content.return_value = mock_response

        ai_service = AIService(api_key="mock-test-key", client=mock_client)
        fin_data = {'monthly_income': 50000.0, 'monthly_expenses': 20000.0}
        res = ai_service.generate_financial_advice(fin_data)

        self.assertTrue(res['success'])
        self.assertEqual(res['source'], 'gemini')
        self.assertIn("## 1. Financial Snapshot", res['content'])
        mock_client.models.generate_content.assert_called_once()

    def test_ai_service_with_mock_exception(self):
        """AI Service gracefully handles client exception without 500 error."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("API Quota Exceeded")

        ai_service = AIService(api_key="mock-test-key", client=mock_client)
        fin_data = {'monthly_income': 50000.0, 'monthly_expenses': 20000.0}
        res = ai_service.generate_financial_advice(fin_data)

        self.assertFalse(res['success'])
        self.assertEqual(res['source'], 'fallback')
        self.assertIn("RuntimeError", res['content'])

    def test_prompt_data_isolation(self):
        """Ensure prompt only includes authorized financial metrics and never secrets."""
        fin_data = {
            'month_name': 'October',
            'year': 2026,
            'monthly_income': 75000.0,
            'monthly_expenses': 32000.0,
            'net_balance': 43000.0,
            'savings_rate': 57.3,
            'monthly_budget': 35000.0,
            'budget_utilization': 91.4,
            'target_savings_rate': 20.0,
            'category_totals': {'Rent': 20000.0, 'Groceries': 7000.0, 'Utilities': 5000.0},
            'recent_transactions': [
                {'date': '2026-10-01', 'type': 'income', 'description': 'Salary', 'amount': 75000.0, 'category_or_source': 'Tech Corp'}
            ]
        }
        prompt = build_financial_prompt(fin_data)

        # Check expected contents
        self.assertIn("₹75,000.00", prompt)
        self.assertIn("57.3%", prompt)
        self.assertIn("Rent: ₹20,000.00", prompt)
        self.assertIn("Tech Corp", prompt)

        # Check absence of confidential tokens
        self.assertNotIn("password_hash", prompt)
        self.assertNotIn("SECRET_KEY", prompt)
        self.assertNotIn("GEMINI_API_KEY", prompt)

    # =========================================================================
    # 6. HTTP END-TO-END SMOKE TESTS
    # =========================================================================
    def test_full_http_smoke_flow(self):
        """End-to-end smoke test executing full navigation and rendering lifecycle."""
        # 1. Unauthenticated root -> redirects to login
        res = self.client.get('/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers['Location'])

        # 2. Login & Register pages render
        self.assertEqual(self.client.get('/login').status_code, 200)
        self.assertEqual(self.client.get('/register').status_code, 200)

        # 3. Register user
        res_reg = self.client.post('/register', data={
            'username': 'E2E Tester',
            'email': 'e2e@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res_reg.status_code, 200)

        # 4. Dashboard renders
        res_dash = self.client.get('/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Financial Dashboard", res_dash.data)

        # 5. Tracker renders
        res_trk = self.client.get('/tracker')
        self.assertEqual(res_trk.status_code, 200)
        self.assertIn(b"Financial Tracker", res_trk.data)

        # 6. AI Insights renders with fallback (no API key configured)
        res_ai = self.client.get('/ai-insights')
        self.assertEqual(res_ai.status_code, 200)
        self.assertIn(b"AI Financial Advisory", res_ai.data)
        self.assertIn(b"Deterministic Financial Intelligence Active", res_ai.data)

        # 7. Logout
        res_out = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(res_out.status_code, 200)
        self.assertIn(b"You have been securely logged out", res_out.data)


if __name__ == '__main__':
    unittest.main()
