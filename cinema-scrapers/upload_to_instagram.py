import requests
import os
import time
import sys

# --- Config ---
# We get these from the GitHub Action environment variables
ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")
IG_USER_ID = os.environ.get("IG_USER_ID")

# The URLs where your files will be live
IMAGE_URL = "https://www.leonelki.com/cinema-scrapers/post_image.png"
CAPTION_URL = "https://www.leonelki.com/cinema-scrapers/post_caption.txt"

def get_caption_text():
    """Fetches the live caption text from your website."""
    try:
        # We use a timestamp to trick the cache and get the fresh file
        r = requests.get(f"{CAPTION_URL}?t={int(time.time())}")
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Error fetching caption: {e}")
        sys.exit(1)

def upload_post():
    if not ACCESS_TOKEN or not IG_USER_ID:
        print("Error: Missing Instagram credentials.")
        sys.exit(1)

    print("1. Fetching caption...")
    caption_text = get_caption_text()

    print("2. Creating Media Container...")
    # Step A: Tell Instagram to download the image
    post_url = f"https://graph.facebook.com/v18.0/{IG_USER_ID}/media"
    payload = {
        "image_url": IMAGE_URL,
        "caption": caption_text,
        "access_token": ACCESS_TOKEN
    }
    
    r = requests.post(post_url, data=payload)
    result = r.json()
    
    if "id" not in result:
        print("Error creating media container:", result)
        sys.exit(1)
        
    creation_id = result["id"]
    print(f"   Container ID: {creation_id}")

    print("3. Waiting for Instagram to process image...")
    # Instagram needs a moment to download and process the image
    time.sleep(15) 

    print("4. Publishing Post...")
    # Step B: Tell Instagram to publish the container
    publish_url = f"https://graph.facebook.com/v18.0/{IG_USER_ID}/media_publish"
    publish_payload = {
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN
    }
    
    r = requests.post(publish_url, data=publish_payload)
    publish_result = r.json()

    if "id" in publish_result:
        print(f"SUCCESS! Post published. ID: {publish_result['id']}")
    else:
        print("Error publishing post:", publish_result)
        sys.exit(1)

if __name__ == "__main__":
    # Optional: Add a small delay to ensure GitHub Pages has propagated the new file
    print("Waiting 60 seconds for GitHub Pages to update...")
    time.sleep(60)
    upload_post()
