
import os
import json
from typing import Dict, List, Optional
from replit import db

class PostDatabase:
    @staticmethod
    def store_post(post: Dict) -> None:
        """Store a published post with timestamp as key"""
        from datetime import datetime
        key = f"post_{datetime.now().isoformat()}"
        db[key] = json.dumps(post)

    @staticmethod
    def get_all_posts() -> List[Dict]:
        """Retrieve all stored posts"""
        posts = []
        for key in db.prefix("post_"):
            try:
                posts.append(json.loads(db[key]))
            except:
                continue
        return posts

    @staticmethod
    def get_latest_post() -> Optional[Dict]:
        """Get the most recently stored post"""
        posts = PostDatabase.get_all_posts()
        return posts[-1] if posts else None

    @staticmethod
    def is_duplicate_article(url: str) -> bool:
        """Check if an article with this URL has been posted before"""
        posts = PostDatabase.get_all_posts()
        return any(post.get('url') == url for post in posts)
