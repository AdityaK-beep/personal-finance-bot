from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.routes.dashboard import calculate_user_monthly_financials
from app.services.ai_service import AIService

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/ai-insights')
@login_required
def ai_insights_view():
    """Generate and display comprehensive personalized AI financial insights."""
    financial_data = calculate_user_monthly_financials(current_user.id)

    ai_service = AIService()
    result = ai_service.generate_financial_advice(financial_data)

    return render_template(
        'ai_insights.html',
        data=financial_data,
        ai_result=result,
        advice_content=result.get('content', ''),
        source=result.get('source', 'fallback')
    )
