import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    is_production = os.getenv("FLASK_ENV") == "production"
    app.run(
        host='127.0.0.1' if is_production else '0.0.0.0',
        port=int(os.getenv("PORT", 5002)),
        debug=not is_production
    )