import os
import requests
import glob
import time
import sys

# --- Configuration ---
# 1. Get secrets from GitHub Actions environment
IG_USER_ID = os.environ.get("IG_USER_ID")
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")

# 2. IMPORTANT: Update this to your actual GitHub Pages URL
# This is required because Instagram API needs a public URL to download the images from.
# Format: "https://[your-github-username].github.io/[your-repo-name]/[subfolder]/"
# Based on your repo (jakobng/website1), this should be:
GITHUB_PAGES_BASE_URL = "https://jakobng.github.io/website1/cinema-scrapers/" 
# <--- ENSURE THIS URL IS CORRECT AND PUBLICLY ACCESSIBLE

API_VERSION = "v21.0"
GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"

# --- API Helper Functions ---

def upload_single_image_container(image_url, caption):
    """Creates a media container for a single image post."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media"
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    response = requests.post(url, data=payload)
    result = response.json()
    
    if "id" not in result:
        print(f"❌ Error creating single container: {result}")
        sys.exit(1)
    
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
    response = requests.post(url, data=payload)
    result = response.json()
    
    if "id" not in result:
        print(f"❌ Error creating carousel child container for {image_url}: {result}")
        sys.exit(1)
        
    print(f"   ↳ Child Container Created: {result['id']}")
    return result["id"]

def create_carousel_parent_container(children_ids, caption):
    """Creates the parent carousel container linking all children (Step 2)."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media"
    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids), # Comma-separated list of IDs
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    response = requests.post(url, data=payload)
    result = response.json()
    
    if "id" not in result:
        print(f"❌ Error creating parent carousel container: {result}")
        sys.exit(1)

    print(f"✅ Created Parent Carousel Container ID: {result['id']}")
    return result["id"]

# --- ASYNCHRONOUS STATUS CHECK ---
def check_media_status(creation_id):
    """Polls the API to check if the media is ready for publishing (Step 3)."""
    url = f"{GRAPH_URL}/{creation_id}"
    params = {
        "fields": "status_code,status,id",
        "access_token": IG_ACCESS_TOKEN
    }

    # Poll status every 5 seconds for up to 60 seconds (12 checks)
    max_checks = 12
    delay = 5  # seconds

    print(f"   Waiting for media ID {creation_id} to finish processing...")

    for i in range(max_checks):
        response = requests.get(url, params=params).json()
        status_code = response.get("status_code")
        
        # Check 1: Final success status
        if status_code == "FINISHED":
            print(f"   Media status: FINISHED. Ready to publish.")
            return True
        
        # Check 2: Fatal error status
        if status_code in ("ERROR", "ERROR_RESOURCE_DOWNLOAD"):
            print(f"❌ Media processing FAILED: {response}")
            return False

        # If still processing, wait and check again
        print(f"   Processing status: {status_code}. Waiting {delay}s...")
        time.sleep(delay)

    print("❌ Timed out waiting for media processing.")
    return False

def publish_media(creation_id):
    """Publishes the container (Step 4)."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": IG_ACCESS_TOKEN
    }
    response = requests.post(url, data=payload)
    result = response.json()
    
    if "id" not in result:
        print(f"❌ Error publishing media: {result}")
        sys.exit(1)
        
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
            print(f"   Processing Child: {filename} -> {image_url}")
            child_id = upload_carousel_child_container(image_url)
            children_ids.append(child_id)
            time.sleep(1) # Small delay between child container creation
        
        # Step 2: Create the parent container linking them
        print("   Linking children to parent container...")
        creation_id = create_carousel_parent_container(children_ids, caption)

    # --- PUBLISH ---
    if creation_id:
        # Step 3: Check status before publishing (Resolves timing error)
        if check_media_status(creation_id):
            # Step 4: Publish
            publish_media(creation_id)
        else:
            print("❌ Publication aborted due to media processing error or timeout.")
            sys.exit(1)

if __name__ == "__main__":
    main()
