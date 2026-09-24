import os
from app import create_app, db

app = create_app()

with app.app_context():
    # Ensure database tables exist on startup (both WSGI server and dev runner)
    db.create_all()

if __name__ == '__main__':

    # Read debug and port configuration safely from environment
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')

    print(f" * Personal Finance Advisor Bot starting on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug_mode)
