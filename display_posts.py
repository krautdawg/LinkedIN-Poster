
from db_manager import PostDatabase

def fetch_and_display_posts():
    all_posts = PostDatabase.get_all_posts()
    if all_posts:
        for index, post in enumerate(all_posts, start=1):
            print(f"Post {index}:")
            print(f"Content: {post.get('content')}")
            print(f"Source URL: {post.get('url')}\n")
    else:
        print("No posts found in the database.")

if __name__ == "__main__":
    fetch_and_display_posts()
