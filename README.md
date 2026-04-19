# Movie Recommender (Flask + SQLite + Collaborative Filtering)

This is a beginner-friendly full-stack app:
- Flask REST APIs (auth, movies, ratings, recommendations, chatbot)
- SQLite database
- Collaborative filtering recommender using cosine similarity
- Bootstrap 5 frontend with 4 pages

## Folder structure
- `backend/`: Flask server + DB init + MovieLens loader
- `frontend/`: HTML templates
- `routes/`: Flask blueprints for REST APIs
- `models/`: SQLite data access + recommender logic
- `static/`: CSS + frontend JavaScript

## 1) Setup

1. Open a terminal in this project folder (`ai project`).
2. Create a Python virtual environment (recommended) and install dependencies:
   - `pip install -r requirements.txt`
3. Initialize the SQLite database:
   - `python -m backend.init_db`

## 2) Load MovieLens sample dataset

MovieLens is downloaded by the loader script.

1. Download + load:
   - `python -m backend.scripts.load_movielens --download`

Optional speed flags (useful for testing):
- Limit users: `python -m backend.scripts.load_movielens --download --max-users 50`
- Limit movies: `python -m backend.scripts.load_movielens --download --max-movies 200`
- Limit ratings rows: `python -m backend.scripts.load_movielens --download --max-ratings 5000`

The loader creates demo user accounts from MovieLens user IDs:
- username: `ml_user_<id>`
- password: `demo-password`

## 3) Run the web app

- `python backend/app.py`

Open:
- `http://localhost:5000/login`

## 4) Using the app

1. Create an account (or use seeded demo users).
2. Browse movies and open the Details page.
3. Use Like/Dislike (or set a 1–5 rating).
4. Go to Dashboard to see:
   - Personal recommendations (with “why recommended”)
   - Group recommendations (enter multiple user IDs)
   - Chatbot suggestions (rule-based, not an LLM)

