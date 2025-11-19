import os
import requests
import glob
import time
import sys

# --- Configuration ---
IG_USER_ID = os.environ.get("IG_USER_ID")
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")

# Update this to your actual GitHub Pages URL if it changed
GITHUB_PAGES_BASE_URL = "https://jakobng.github.io/website1/cinema-scrapers/" 

API_VERSION = "v21.0"
GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"

def post_request_with_retry(url, payload, description="API Request", max_retries=5):
    """
    Makes a POST request with automatic retries for transient errors (Code 1, 2, 4, 17, 341).
    """
    for attempt in range(max_retries):
        try:
            response = requests.post(url, data=payload, timeout=30)
            result = response.json()
            
            # Success case
            if "id" in result:
                return result
            
            # Error handling
            error = result.get("error", {})
            code = error.get("code")
            subcode = error.get("error_subcode")
            message = error.get("message")
            
            print(f"   ⚠️ {description} Failed (Attempt {attempt+1}/{max_retries})")
            print(f"      Error {code} (Subcode {subcode}): {message}")
            
            # Retry on common transient errors:
            # 1: Unknown error (your current issue)
            # 2: Service temporarily unavailable
            # 4: Rate limit (sometimes temporary)
            # 17: User request limit
            # 341: Feed action limit
            # 99 (Subcode): Unknown
            if code in [1, 2, 4, 17, 341] or subcode in [99, 2207051]:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 15  # 15s, 30s, 45s, 60s...
                    print(f"      ⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
            
            # If it's a fatal error (like invalid token), stop immediately
            print("      ❌ Fatal Error. Stopping.")
            sys.exit(1)
            
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Network Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
            sys.exit(1)
            
    print(f"❌ Failed {description} after {max_retries} attempts.")
    sys.exit(1)

def upload_single_image_container(image_url, caption):
    """Creates a media container for a single image post."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media"
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    result = post_request_with_retry(url, payload, description="Create Single Container")
    print(f"✅ Created Single Container ID: {result['id']}")
    return result["id"]

def upload_carousel_child_container(image_url):
    """Creates a child container for an item inside a carousel."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media"
    payload = {
        "image_url": image_url,
        "is_carousel_item": "true",
        "access_token": IG_ACCESS_TOKEN
    }
    # Helper extracts filename for log
    filename = image_url.split('/')[-1]
    result = post_request_with_retry(url, payload, description=f"Upload Child {filename}")
    
    print(f"   ↳ Container Created: {result['id']}")
    return result["id"]

def create_carousel_parent_container(children_ids, caption):
    """Creates the parent carousel container linking all children."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media"
    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    result = post_request_with_retry(url, payload, description="Create Parent Carousel")
    
    print(f"✅ Created Parent Carousel Container ID: {result['id']}")
    return result["id"]

def check_media_status(creation_id):
    """Polls the API to check if the media is ready for publishing."""
    url = f"{GRAPH_URL}/{creation_id}"
    params = {
        "fields": "status_code,status,id",
        "access_token": IG_ACCESS_TOKEN
    }

    max_checks = 20
    delay = 10  # Slower polling to be safe

    print(f"   Waiting for media ID {creation_id} to finish processing...")

    for i in range(max_checks):
        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            status_code = data.get("status_code")
            
            if status_code == "FINISHED":
                print(f"   Media status: FINISHED. Ready to publish.")
                return True
            
            if status_code in ("ERROR", "ERROR_RESOURCE_DOWNLOAD"):
                print(f"❌ Media processing FAILED: {data}")
                return False

            print(f"   Processing status: {status_code}. Waiting {delay}s...")
            time.sleep(delay)
            
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Network Check Error: {e}")
            time.sleep(delay)

    print("❌ Timed out waiting for media processing.")
    return False

def publish_media(creation_id):
    """Publishes the container."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": IG_ACCESS_TOKEN
    }
    result = post_request_with_retry(url, payload, description="Publish Media")
    
    print(f"🚀 SUCCESS! Published to Instagram. Post ID: {result['id']}")
    return result["id"]

def main():
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        print("❌ Missing IG_USER_ID or IG_ACCESS_TOKEN environment variables.")
        sys.exit(1)

    # 1. Read Caption
    try:
        with open("post_caption.txt", "r", encoding="utf-8") as f:
            caption = f.read()
    except FileNotFoundError:
        print("❌ post_caption.txt not found.")
        sys.exit(1)

    # 2. Find Image Files
    image_files = sorted(glob.glob("post_image_*.png"))
    
    # Fallback
    if not image_files and os.path.exists("post_image.png"):
        image_files = ["post_image.png"]

    if not image_files:
        print("❌ No image files found to upload.")
        sys.exit(1)

    print(f"📸 Found {len(image_files)} images: {image_files}")

    creation_id = None

    # --- SINGLE IMAGE MODE ---
    if len(image_files) == 1:
        print("🔹 Detected Single Image Mode")
        filename = image_files[0]
        image_url = f"{GITHUB_PAGES_BASE_URL}{filename}"
        print(f"   Public URL: {image_url}")
        
        creation_id = upload_single_image_container(image_url, caption)

    # --- CAROUSEL MODE ---
    else:
        print(f"🔹 Detected Carousel Mode ({len(image_files)} slides)")
        
        # Step 1: Create containers for each image (Children)
        children_ids = []
        for filename in image_files:
            image_url = f"{GITHUB_PAGES_BASE_URL}{filename}"
            print(f"   Processing Child: {filename}")
            
            child_id = upload_carousel_child_container(image_url)
            children_ids.append(child_id)
            
            # Increased delay to prevent "Unknown Error" rate limiting
            time.sleep(5) 
        
        # Step 2: Create the parent container linking them
        print("   Linking children to parent container...")
        creation_id = create_carousel_parent_container(children_ids, caption)

    # --- PUBLISH ---
    if creation_id:
        # Step 3: Check status before publishing
        if check_media_status(creation_id):
            # Step 4: Publish
            publish_media(creation_id)
        else:
            print("❌ Publication aborted due to media processing error or timeout.")
            sys.exit(1)

if __name__ == "__main__":
    main()
