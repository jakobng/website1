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
# Format: "https://[your-github-username].github.io/[your-repo-name]/"
GITHUB_PAGES_BASE_URL = "https://jakobng.github.io/website1/cinema-scrapers/"

API_VERSION = "v21.0"
GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"

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
    """Creates the parent carousel container linking all children."""
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

def publish_media(creation_id):
    """Publishes the container (single or carousel) to the feed."""
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
    # Look for files matching pattern 'post_image_*.png' (e.g., post_image_00.png, post_image_01.png)
    image_files = sorted(glob.glob("post_image_*.png"))
    
    # Fallback for legacy single file name
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
        # Construct public URL
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
            # Small delay to be nice to the API
            time.sleep(1) 
        
        # Step 2: Create the parent container linking them
        print("   Linking children to parent container...")
        creation_id = create_carousel_parent_container(children_ids, caption)

    # --- PUBLISH ---
    # Step 3: Publish the container (applies to both Single and Carousel)
    if creation_id:
        print("   Publishing...")
        publish_media(creation_id)

if __name__ == "__main__":
    main()
