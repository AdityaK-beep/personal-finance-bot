import os
import math
from typing import Dict, Any, Optional

SYSTEM_INSTRUCTION = """You are an expert, empathetic Personal Finance Advisor.

Analyze only the financial information provided in the request.

Do not invent transactions, income, debts, investments, or personal circumstances.

Provide practical and understandable financial guidance.

Identify observable spending patterns.

Address:

1. Overspending detection
2. Budget allocation
3. Comparison with the 50/30/20 framework
4. Concrete saving suggestions
5. Important financial patterns
6. Budget risks
7. Suggested next actions

Adapt recommendations to the user's observed financial pattern.

Potential user personas include:

- Salaried Professional
- College Student
- Freelancer / Variable Income
- Household Manager

Do not assume a persona unless the data supports it.

For variable income, avoid assuming a fixed monthly salary.

For students, prioritize realistic small-scale savings.

For households, consider recurring category-level spending.

For salaried professionals, consider recurring expenses and goal-oriented savings.

Do not shame the user.

Do not present speculative claims as facts.

Do not provide personalized investment, tax, legal, or regulated financial advice as if you were a licensed professional.

Clearly distinguish:
- observations
- calculations
- recommendations

Use concise headings and bullet points."""


def build_financial_prompt(data: Dict[str, Any]) -> str:
    """Build a structured text prompt containing only authenticated user financial data."""
    categories_text = "\n".join(
        [f"  - {cat}: ₹{data.get('category_totals', {}).get(cat, 0.0):,.2f}"
         for cat in ['Rent', 'Groceries', 'Transport', 'Entertainment', 'Utilities', 'Other']]
    )

    transactions_text = ""
    recent_txs = data.get('recent_transactions', [])
    if recent_txs:
        tx_lines = [
            f"  - [{tx['date']}] {tx['type'].upper()}: {tx['description']} (₹{tx['amount']:,.2f}, {tx.get('category_or_source', '')})"
            for tx in recent_txs[:10]
        ]
        transactions_text = "\n".join(tx_lines)
    else:
        transactions_text = "  - No recent transactions recorded."

    prompt = f"""USER FINANCIAL PROFILE

Current Month & Year:
{data.get('month_name', 'Current Month')} {data.get('year', '')}

Monthly Income:
₹{data.get('monthly_income', 0.0):,.2f}

Monthly Expenses:
₹{data.get('monthly_expenses', 0.0):,.2f}

Net Balance:
₹{data.get('net_balance', 0.0):,.2f}

Savings Rate:
{data.get('savings_rate', 0.0):.1f}%

Monthly Budget Limit:
₹{data.get('monthly_budget', 0.0):,.2f}

Budget Utilization:
{data.get('budget_utilization', 0.0):.1f}%

Target Savings Rate:
{data.get('target_savings_rate', 20.0):.1f}%

Expense Categories:
{categories_text}

Recent Transactions:
{transactions_text}

Please provide an empathetic, structured financial evaluation using these specific sections:
## 1. Financial Snapshot
## 2. Overspending Detection
## 3. Budget Allocation
## 4. 50/30/20 Comparison
## 5. Saving Suggestions
## 6. Key Observations
## 7. Suggested Next Steps

Remember: The 50/30/20 rule is a guiding benchmark (50% Needs, 30% Wants, 20% Savings), not an absolute law.
Do not invent unprovided data.
"""
    return prompt


def generate_local_fallback(data: Dict[str, Any], reason: str = "") -> str:
    """Generate a reliable, deterministic local financial advisory report when AI is unavailable."""
    income = data.get('monthly_income', 0.0)
    expenses = data.get('monthly_expenses', 0.0)
    balance = data.get('net_balance', 0.0)
    savings_rate = data.get('savings_rate', 0.0)
    budget = data.get('monthly_budget', 0.0)
    budget_usage = data.get('budget_utilization', 0.0)
    cat_totals = data.get('category_totals', {})

    # Top spending category
    sorted_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
    top_cat = sorted_cats[0] if sorted_cats and sorted_cats[0][1] > 0 else ("None", 0.0)

    # 50/30/20 estimation
    needs = cat_totals.get('Rent', 0.0) + cat_totals.get('Groceries', 0.0) + cat_totals.get('Utilities', 0.0)
    wants = cat_totals.get('Entertainment', 0.0) + cat_totals.get('Transport', 0.0) + cat_totals.get('Other', 0.0)
    saved = max(0.0, balance)

    needs_pct = (needs / income * 100) if income > 0 else 0
    wants_pct = (wants / income * 100) if income > 0 else 0
    saved_pct = savings_rate if income > 0 else 0

    reason_note = f"\n*Notice: {reason} Showing rule-based local financial analysis.*" if reason else ""

    report = f"""## 1. Financial Snapshot{reason_note}
* **Total Monthly Income:** ₹{income:,.2f}
* **Total Monthly Expenses:** ₹{expenses:,.2f}
* **Net Cash Flow / Balance:** ₹{balance:,.2f}
* **Current Savings Rate:** {savings_rate:.1f}%

## 2. Overspending Detection
"""
    if expenses > income and income > 0:
        report += f"* **Deficit Alert:** Your spending exceeds your income by ₹{abs(balance):,.2f}. This indicates a cash burn phase that depletes savings.\n"
    elif budget > 0 and expenses > budget:
        report += f"* **Budget Overage:** You have spent ₹{expenses:,.2f}, surpassing your monthly budget limit of ₹{budget:,.2f} by ₹{(expenses - budget):,.2f} ({budget_usage:.1f}% used).\n"
    elif expenses == 0 and income == 0:
        report += "* **No Activity:** No income or expenses recorded yet for this billing cycle. Add entries to trigger active detection.\n"
    else:
        report += f"* **Stable Spending:** Expenses are currently within recorded income. Your highest spending area is **{top_cat[0]}** (₹{top_cat[1]:,.2f}).\n"

    report += f"""
## 3. Budget Allocation
* **Monthly Budget Limit:** ₹{budget:,.2f}
* **Budget Used:** {budget_usage:.1f}% of allocated ceiling
* **Top Outflow Category:** {top_cat[0]} (₹{top_cat[1]:,.2f})

## 4. 50/30/20 Comparison
*The 50/30/20 guideline suggests allocating roughly 50% to essential Needs, 30% to discretionary Wants, and 20% to Savings/Debt reduction.*
* **Essential Needs (Rent, Groceries, Utilities):** ₹{needs:,.2f} ({needs_pct:.1f}% of income vs 50% target)
* **Discretionary Wants (Entertainment, Transport, Other):** ₹{wants:,.2f} ({wants_pct:.1f}% of income vs 30% target)
* **Savings / Net Buffer:** ₹{saved:,.2f} ({saved_pct:.1f}% of income vs 20% target)

## 5. Saving Suggestions
"""
    if savings_rate < 10 and income > 0:
        report += "* Target low-hanging fruit in discretionary categories such as **Entertainment** or **Other**.\n"
        report += "* Consider implementing automated transfers of 5–10% of income directly into a dedicated savings reserve immediately upon receipt.\n"
    else:
        report += f"* Maintain your positive cash flow. Continue directing surplus towards your emergency fund (aiming for 3–6 months of essential living expenses: ~₹{(needs * 3):,.2f}).\n"
        report += f"* Review the **{top_cat[0]}** category periodically to check if bulk purchase or alternative service providers could reduce unit costs.\n"

    report += """
## 6. Key Observations
* Your financial profile has been evaluated based strictly on the current month's recorded transaction history.
* Maintaining a steady tracking habit allows finer trend analysis and helps calibrate realistic monthly budget ceilings.

## 7. Suggested Next Steps
* 1. Set or calibrate your monthly budget goal in the Tracker tab.
* 2. Log upcoming daily expenses promptly to prevent untracked cash leakage.
* 3. Aim to keep non-essential spending below 30% of total earnings.
"""
    return report.strip()


def get_quick_insight(data: Dict[str, Any]) -> str:
    """Return a brief 1-2 sentence deterministic insight for dashboard badges and widgets."""
    income = data.get('monthly_income', 0.0)
    expenses = data.get('monthly_expenses', 0.0)
    budget = data.get('monthly_budget', 0.0)
    savings_rate = data.get('savings_rate', 0.0)

    if income == 0 and expenses == 0:
        return "Welcome! Start by adding your monthly income and first expenses in the Tracker."
    if expenses > income and income > 0:
        return f"Warning: Monthly spending (₹{expenses:,.2f}) exceeds total income by ₹{(expenses - income):,.2f}. Trim discretionary costs."
    if budget > 0 and expenses > budget:
        return f"Budget alert: You have reached {data.get('budget_utilization', 0.0):.0f}% of your monthly spending limit."
    if savings_rate >= data.get('target_savings_rate', 20.0):
        return f"Great job! You've achieved a {savings_rate:.1f}% savings rate this month, meeting your savings target."
    return f"On track: Net surplus is ₹{(income - expenses):,.2f} with {savings_rate:.1f}% saved. Keep logging daily expenses."


class AIService:
    """Service wrapping Google GenAI SDK with fallback, testability, and error handling."""

    def __init__(self, api_key: Optional[str] = None, client: Optional[Any] = None):
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY', '').strip()
        self._client = client

    def get_client(self):
        """Lazy-initialize or return the GenAI client."""
        if self._client is not None:
            return self._client

        if not self.api_key:
            return None

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            return self._client
        except Exception:
            return None

    def generate_financial_advice(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive financial advice using Gemini or graceful fallback."""
        # Check API key presence
        if not self.api_key:
            return {
                "success": False,
                "source": "fallback",
                "content": generate_local_fallback(
                    financial_data,
                    reason="Gemini API key is not configured in .env."
                )
            }

        client = self.get_client()
        if not client:
            return {
                "success": False,
                "source": "fallback",
                "content": generate_local_fallback(
                    financial_data,
                    reason="Gemini client initialization failed."
                )
            }

        prompt = build_financial_prompt(financial_data)

        try:
            from google.genai import types

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.3,
                    max_output_tokens=2048,
                )
            )

            # Validate response
            if response and hasattr(response, 'text') and response.text:
                return {
                    "success": True,
                    "source": "gemini",
                    "content": response.text.strip()
                }
            else:
                return {
                    "success": False,
                    "source": "fallback",
                    "content": generate_local_fallback(
                        financial_data,
                        reason="Gemini returned an empty or unparseable response."
                    )
                }

        except Exception as e:
            # Handle rate limits, network timeouts, invalid keys gracefully without 500 error
            return {
                "success": False,
                "source": "fallback",
                "content": generate_local_fallback(
                    financial_data,
                    reason=f"Gemini API request encountered an error ({type(e).__name__})."
                )
            }
