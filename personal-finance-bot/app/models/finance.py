from datetime import date
from app import db

ALLOWED_CATEGORIES = [
    'Rent',
    'Groceries',
    'Transport',
    'Entertainment',
    'Utilities',
    'Other'
]


class Income(db.Model):
    """Income record for tracking user earnings."""
    __tablename__ = 'income'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    source = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)

    def validate(self) -> None:
        """Validate income model constraints."""
        if not self.source or not self.source.strip():
            raise ValueError("Income source is required.")
        if self.amount is None or self.amount <= 0:
            raise ValueError("Income amount must be greater than 0.")
        if not self.date:
            raise ValueError("Income date is required.")

    def __repr__(self):
        return f"<Income {self.source}: ₹{self.amount:.2f} on {self.date}>"


class Expense(db.Model):
    """Expense record for tracking categorized spending."""
    __tablename__ = 'expense'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)

    def validate(self) -> None:
        """Validate expense model constraints."""
        if not self.title or not self.title.strip():
            raise ValueError("Expense title is required.")
        if self.amount is None or self.amount <= 0:
            raise ValueError("Expense amount must be greater than 0.")
        if self.category not in ALLOWED_CATEGORIES:
            raise ValueError(f"Invalid category '{self.category}'. Allowed categories: {', '.join(ALLOWED_CATEGORIES)}")
        if not self.date:
            raise ValueError("Expense date is required.")

    def __repr__(self):
        return f"<Expense {self.title} ({self.category}): ₹{self.amount:.2f} on {self.date}>"


class BudgetGoal(db.Model):
    """User monthly budget and target savings rate."""
    __tablename__ = 'budget_goal'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True, index=True)
    monthly_limit = db.Column(db.Float, default=0.0, nullable=False)
    target_savings_rate = db.Column(db.Float, default=20.0, nullable=False)

    def validate(self) -> None:
        """Validate budget goal constraints."""
        if self.monthly_limit is None or self.monthly_limit < 0:
            raise ValueError("Monthly budget limit must be greater than or equal to 0.")
        if self.target_savings_rate is None or not (0 <= self.target_savings_rate <= 100):
            raise ValueError("Target savings rate must be between 0% and 100%.")

    def __repr__(self):
        return f"<BudgetGoal Limit: ₹{self.monthly_limit:.2f}, Target Savings: {self.target_savings_rate:.1f}%>"
