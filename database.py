
from replit import db
from typing import Dict, Optional
from datetime import datetime

class LinkedInPostDB:
    @staticmethod
    def store_post(post_content: str, source_url: str, post_id: Optional[str] = None) -> None:
        """Store a LinkedIn post with timestamp"""
        timestamp = datetime.now().isoformat()
        post_data = {
            "content": post_content,
            "source_url": source_url,
            "timestamp": timestamp,
            "linkedin_post_id": post_id
        }
        db[f"linkedin_post_{timestamp}"] = post_data

    @staticmethod
    def get_all_posts() -> Dict:
        """Retrieve all LinkedIn posts"""
        return {key: db[key] for key in db.keys() if key.startswith("linkedin_post_")}

    @staticmethod
    def get_latest_post() -> Optional[Dict]:
        """Get the most recent LinkedIn post"""
        posts = LinkedInPostDB.get_all_posts()
        if not posts:
            return None
        latest_key = max(posts.keys())
        return db[latest_key]
