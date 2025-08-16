from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import random
import logging

logger = logging.getLogger("uvicorn.error")
app = FastAPI()

# Абсолютные пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Файлы
ARTICLES_JSON = os.path.join(DATA_DIR, "articles.json")
THEMES_JSON = os.path.join(DATA_DIR, "themes.json")
RECENT_JSON = os.path.join(DATA_DIR, "recent.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def normalize_theme(theme):
    return theme.strip().lower() if theme else None


def get_all_articles():
    if not os.path.exists(ARTICLES_JSON):
        logger.warning("articles.json не найден")
        return []
    try:
        with open(ARTICLES_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения articles.json: {e}")
        return []


@app.get("/api/themes")
async def get_themes():
    if not os.path.exists(THEMES_JSON):
        return []
    with open(THEMES_JSON, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/recent_articles")
async def get_recent_articles(count: int = 9, except_articles: list[int] = Query(default=[])):
    if not os.path.exists(RECENT_JSON):
        return []
    with open(RECENT_JSON, encoding="utf-8") as f:
        articles = json.load(f)

    filtered = [a for a in articles if a.get("id") not in except_articles]
    selected = random.sample(filtered, min(count, len(filtered)))
    return selected


@app.get("/api/random_articles")
def get_random_articles(count: int = 9, theme: str = Query(None), except_articles: list[int] = Query(default=[])):
    all_articles = get_all_articles()
    if not all_articles:
        return JSONResponse(status_code=500, content={"error": "Список статей пуст или недоступен"})

    theme = normalize_theme(theme)
    logger.debug(f"theme: {theme}")
    filtered = []
    if theme:
        for a in all_articles:
            atheme = a.get("theme")
            logger.debug(f"theme: {theme}, a.theme: {atheme}")
            if normalize_theme(atheme) == theme:
                filtered.append(a)
        #filtered = [a for a in all_articles if normalize_theme(a.get("theme")) == theme]
    else:
        filtered = all_articles
    
    filtered = [a for a in filtered if a.get("id") not in except_articles]
    
    if not filtered:
        return []

    chosen = random.sample(filtered, min(count, len(filtered)))
    result = []

    for a in chosen:
        image = a.get("image")
        #if not image or not os.path.exists(os.path.join(BASE_DIR, image.replace("/", os.sep))):
        if not image:
            image = "images/default.jpg"
        else:
            image = image.replace("\\", "/").lstrip("/")

        result.append({
            "slug": a["slug"],
            "title": a["title"].strip('"'),
            "theme": a.get("theme"),
            "intro": a.get("intro", "Описание недоступно"),
            "id" : a.get("id"),
            "image": image
        })

    return result


@app.get("/api/look_for_articles")
def look_for_articles(q: str, count: int = 9, except_articles: list[int] = Query(default=[])):
    all_articles = get_all_articles()
    if not q:
        return []
    
    q = q.lower()

    def matches(article):
        title = article.get("title", "").lower()
        intro = article.get("intro", "").lower()
        keywords = article.get("keywords", [])
        keywords_str = " ".join(keywords).lower() if isinstance(keywords, list) else ""
        return q in title or q in intro or q in keywords_str

    result = [a for a in all_articles if matches(a) and a.get("id") not in except_articles]

    return result[:count]



@app.get("/api/similar_articles")
def get_similar_articles(slug: str, limit: int = 3, except_articles: list[int] = Query(default=[])):
    if not os.path.exists(ARTICLES_JSON):
        return JSONResponse(status_code=500, content={"error": "articles.json не найден"})

    try:
        with open(ARTICLES_JSON, "r", encoding="utf-8") as f:
            articles = json.load(f)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Ошибка чтения articles.json"})

    base_article = next((a for a in articles if a["slug"] == slug), None)
    if not base_article:
        return JSONResponse(status_code=404, content={"error": "Статья не найдена"})

    base_keywords = set(map(str.lower, base_article.get("keywords", [])))
    similar = []

    # Ищем похожие
    if base_keywords:
        for a in articles:
            if a["slug"] == slug or a.get("id") in except_articles:
                continue
            article_keywords = set(map(str.lower, a.get("keywords", [])))
            if base_keywords.intersection(article_keywords):
                similar.append(a)

    # Если похожих меньше limit, добавляем рандомные
    if len(similar) < limit:
        needed = limit - len(similar)
        excluded_slugs = {slug} | {a["slug"] for a in similar}
        candidates = [a for a in articles if a["slug"] not in excluded_slugs and a.get("id") not in except_articles]
        random_articles = random.sample(candidates, min(needed, len(candidates)))
        similar.extend(random_articles)

    similar = similar[:limit]

    result = []
    for article in similar:
        image_path = article.get("image")
        if not image_path or not os.path.exists(os.path.join(BASE_DIR, image_path.replace("/", os.sep))):
            image_path = "images/default.jpg"
        else:
            filename = os.path.basename(image_path)
            image_path = f"images/{filename}"

        result.append({
            "slug": article["slug"],
            "title": article["title"].strip('"'),
            "intro": article.get("intro", "Краткое описание недоступно"),
            "image": image_path
        })

    return result
