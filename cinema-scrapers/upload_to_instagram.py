import os
import requests
import glob
import time
import sys
import argparse

# --- Configuration ---
IG_USER_ID = os.environ.get("IG_USER_ID")
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")

# Point to the new folder in the URL so Instagram can download them
GITHUB_PAGES_BASE_URL = "https://jakobng.github.io/website1/cinema-scrapers/ig_posts/" 

API_VERSION = "v21.0"
GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"

# Define local paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "ig_posts")

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
    """Creates a container for a single item (slide) inside a carousel."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media"
    payload = {
        "image_url": image_url,
        "is_carousel_item": "true",
        "access_token": IG_ACCESS_TOKEN
    }
    response = requests.post(url, data=payload)
    result = response.json()

    if "id" not in result:
        print(f"❌ Error creating child container: {result}")
        return None
        
    return result["id"]

def create_carousel_container(child_ids, caption):
    """Bundles child containers into a carousel post."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media"
    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(child_ids),
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    response = requests.post(url, data=payload)
    result = response.json()

    if "id" not in result:
        print(f"❌ Error creating carousel container: {result}")
        sys.exit(1)

    print(f"✅ Created Carousel Container ID: {result['id']}")
    return result["id"]

def upload_story_container(image_url):
    """Creates a media container for a STORY."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media"
    payload = {
        "image_url": image_url,
        "media_type": "STORIES",
        "access_token": IG_ACCESS_TOKEN
    }
    response = requests.post(url, data=payload)
    result = response.json()
    
    if "id" not in result:
        print(f"❌ Error creating story container: {result}")
        return None
    
    print(f"✅ Created Story Container ID: {result['id']}")
    return result["id"]

def publish_media(creation_id):
    """Publishes a container."""
    url = f"{GRAPH_URL}/{IG_USER_ID}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": IG_ACCESS_TOKEN
    }
    response = requests.post(url, data=payload)
    result = response.json()
    
    if "id" in result:
        print(f"🚀 Published! Media ID: {result['id']}")
        return True
    else:
        print(f"❌ Error publishing: {result}")
        return False

def check_media_status(container_id):
    """Checks if the container is ready to publish."""
    url = f"{GRAPH_URL}/{container_id}"
    params = {
        "fields": "status_code,status",
        "access_token": IG_ACCESS_TOKEN
    }
    
    # Poll for up to 60 seconds
    for _ in range(6):
        response = requests.get(url, params=params)
        data = response.json()
        status = data.get("status_code")
        
        if status == "FINISHED":
            return True
        elif status == "ERROR":
            print(f"❌ Container failed processing: {data}")
            return False
            
        print(f"⏳ Processing... ({status})")
        time.sleep(5)
        
    print("❌ Timed out waiting for media processing.")
    return False

# --- Main Logic ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["cinema", "movie"], required=True, help="Type of post to upload")
    args = parser.parse_args()
    
    POST_TYPE = args.type
    
    print(f"Starting Upload Process for Mode: {POST_TYPE}")

    # 1. Locate Files based on Type
    if POST_TYPE == "cinema":
        # Cinema Mode (V1): post_image_XX.png
        post_pattern = os.path.join(OUTPUT_DIR, "post_image_*.png")
        story_pattern = os.path.join(OUTPUT_DIR, "story_image_*.png")
        caption_path = os.path.join(OUTPUT_DIR, "post_caption.txt")
        
    elif POST_TYPE == "movie":
        # Movie Mode (V2): post_v2_image_XX.png
        post_pattern = os.path.join(OUTPUT_DIR, "post_v2_image_*.png")
        story_pattern = os.path.join(OUTPUT_DIR, "story_v2_image_*.png")
        caption_path = os.path.join(OUTPUT_DIR, "post_v2_caption.txt")
        
    post_files = sorted(glob.glob(post_pattern))
    story_files = sorted(glob.glob(story_pattern))
    
    # 2. Read Caption
    caption = "Cinema Schedule"
    if os.path.exists(caption_path):
        with open(caption_path, "r", encoding="utf-8") as f:
            caption = f.read()
    else:
        print("⚠️ No caption file found, using default.")

    # 3. Generate Cache Buster
    # This ensures Instagram fetches the NEWEST version of the file from GitHub Pages,
    # bypassing any CDN caching of yesterday's file.
    cache_buster = int(time.time())

    # --- FEED POST ---
    print("\n--- PROCESSING FEED POST ---")
    
    if not post_files:
        print(f"❌ No post images found for mode '{POST_TYPE}'. Exiting.")
        sys.exit(1)
        
    if len(post_files) == 1:
        # Single Image
        filename = os.path.basename(post_files[0])
        image_url = f"{GITHUB_PAGES_BASE_URL}{filename}?v={cache_buster}"
        print(f"Preparing Single Post: {filename}")
        
        container_id = upload_single_image_container(image_url, caption)
        if check_media_status(container_id):
            publish_media(container_id)
            
    else:
        # Carousel
        print(f"Detected {len(post_files)} images. Preparing Carousel...")
        child_ids = []
        
        for local_path in post_files:
            filename = os.path.basename(local_path)
            image_url = f"{GITHUB_PAGES_BASE_URL}{filename}?v={cache_buster}"
            print(f"   Uploading slide: {filename}")
            
            c_id = upload_carousel_child_container(image_url)
            if c_id:
                child_ids.append(c_id)
            else:
                print("   Skipping failed slide.")
        
        if child_ids:
            carousel_id = create_carousel_container(child_ids, caption)
            if check_media_status(carousel_id):
                publish_media(carousel_id)
        else:
            print("❌ No valid slides uploaded.")

    # --- STORY MODE ---
    print("\n--- CHECKING FOR STORIES ---")
    
    if story_files:
        print(f"🔹 Detected {len(story_files)} Story Images. Starting sequence upload...")
        
        for i, local_path in enumerate(story_files):
            filename = os.path.basename(local_path)
            # Use the NEW URL structure with cache buster
            image_url = f"{GITHUB_PAGES_BASE_URL}{filename}?v={cache_buster}"
            print(f"\n   Story {i+1}/{len(story_files)}: {filename}")
            
            # 1. Create Container
            container_id = upload_story_container(image_url)
            
            if container_id:
                # 2. Check Status
                if check_media_status(container_id):
                    # 3. Publish Immediately
                    result = publish_media(container_id)
                    
                    if result:
                        print(f"   ✅ Story {i+1} published.")
                        # 4. Nap (Rate Limit Protection)
                        print("   ⏳ Sleeping 10s to be gentle on API...")
                        time.sleep(10)
                    else:
                        print(f"   ❌ Story {i+1} failed to publish.")
            else:
                print(f"   Skipping Story {filename} due to container error.")
                
    else:
        print(f"ℹ️ No story images found for mode '{POST_TYPE}'. Skipping Story sequence.")

if __name__ == "__main__":
    main()
