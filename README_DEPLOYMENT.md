# Deployment Options

## Option 1: Vercel (Current Setup)
**Pros**: Free, easy CI/CD
**Cons**: Database resets on each deployment

### Steps:
```bash
vercel
# Follow prompts, set environment variables in dashboard
```

### Environment Variables Needed:
- FLASK_SECRET_KEY (set to random string)
- FLASK_DEBUG=0

### Post-Deployment:
Run database initialization locally or use external database.

---

## Option 2: PythonAnywhere (Recommended for Beginners)
**Pros**: Persistent database, easier setup
**Cons**: Limited free tier

### Steps:
1. Sign up at pythonanywhere.com
2. Create "Web App" -> Flask
3. Upload files via Web UI or Git
4. Install requirements in virtual environment
5. Set up database in /home/username/

---

## Option 3: Railway (Modern Alternative)
**Pros**: Persistent database, good free tier
**Cons**: More complex setup

### Steps:
```bash
railway login
railway init
railway up
```

---

## Option 4: Render (Simple Alternative)
**Pros**: Free PostgreSQL, easy setup
**Cons**: Limited free tier

### Steps:
1. Connect GitHub repo to render.com
2. Select Flask as framework
3. Set environment variables
4. Deploy automatically

---

## Quick Fix for Current Vercel Setup:
Use external database (like PostgreSQL) instead of SQLite for production.
