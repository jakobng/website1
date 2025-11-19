import os
import sys
import time
import requests
import glob
import argparse

# --- Configuration ---
IG_USER_ID = os.environ.get("IG_USER_ID")
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")
BASE_URL = "https://graph.facebook.com/v18.0"

def check_api_limit(response):
    """Checks headers for API usage and prints warnings."""
    if "x-app-usage" in response.headers:
        # x-app-usage returns usage percentage: {"call_count":10, "total_time":5...}
        print(f"   [API Usage Status] {response.headers['x-app-usage']}")

def upload_single_image(image_path, caption=""):
    """Uploads a single image to a container."""
    url = f"{BASE_URL}/{IG_USER_ID}/media"
    
    repo = os.environ.get('GITHUB_REPOSITORY')
    filename = os.path.basename(image_path)
    # RAW github url so Instagram can fetch it
    image_url = f"https://raw.githubusercontent.com/{repo}/main/cinema-scrapers/{filename}"

    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    
    if not caption: 
        params["is_carousel_item"] = "true"

    r = requests.post(url, params=params)
    check_api_limit(r)
    
    if r.status_code != 200:
        print(f"❌ Error uploading {filename}: {r.text}")
        return None
        
    container_id = r.json().get("id")
    print(f"   ↳ Container Created: {container_id}")
    return container_id

def create_carousel_container(children_ids, caption):
    """Creates the parent container for the carousel."""
    url = f"{BASE_URL}/{IG_USER_ID}/media"
    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    r = requests.post(url, params=params)
    check_api_limit(r)
    
    if r.status_code != 200:
        print(f"❌ Error creating carousel parent: {r.text}")
        return None
    return r.json().get("id")

def publish_media(creation_id):
    """Publishes the container."""
    url = f"{BASE_URL}/{IG_USER_ID}/media_publish"
    params = {
        "creation_id": creation_id,
        "access_token": IG_ACCESS_TOKEN
    }
    
    # RETRY LOGIC
    max_retries = 3
    for i in range(max_retries):
        print(f"   🚀 Attempting to publish (Attempt {i+1}/{max_retries})...")
        r = requests.post(url, params=params)
        check_api_limit(r)
        
        if r.status_code == 200:
            print("   ✅ SUCCESS: Published to Instagram!")
            return True
        
        error_data = r.json().get("error", {})
        subcode = error_data.get("error_subcode")
        message = error_data.get("message")
        
        print(f"   ⚠️ Publish Failed: {message} (Subcode: {subcode})")

        # Rate Limit Error
        if subcode == 2207051:
            wait_time = 120 # Wait 2 minutes if rate limited
            print(f"   ⏳ RATE LIMITED. Sleeping {wait_time}s...")
            time.sleep(wait_time)
        elif subcode == 2207085: # Fatal / Locked
             print("   ❌ FATAL error. Container is locked/invalid. Stopping.")
             return False
        else:
            print("   ⏳ Generic error. Retrying in 30 seconds...")
            time.sleep(30)
            
    return False

def wait_for_processing(container_id):
    """Checks status until FINISHED."""
    url = f"{BASE_URL}/{container_id}"
    params = {"fields": "status_code", "access_token": IG_ACCESS_TOKEN}
    
    print(f"   Waiting for media ID {container_id} to process...")
    
    for _ in range(20): 
        r = requests.get(url, params=params)
        status = r.json().get("status_code")
        
        if status == "FINISHED":
            print("   Media status: FINISHED. Ready to publish.")
            return True
        elif status == "ERROR":
            print("   Media status: ERROR.")
            return False
            
        print("   ... processing (sleeping 10s)")
        time.sleep(10) 
        
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--is_carousel", action="store_true")
    args = parser.parse_args()

    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        print("❌ Missing IG credentials.")
        sys.exit(1)

    try:
        with open("post_caption.txt", "r", encoding="utf-8") as f:
            caption = f.read()
    except FileNotFoundError:
        caption = "Today's Showtimes"

    images = sorted(glob.glob("post_image_*.png"))
    
    if not images:
        print("❌ No images found.")
        sys.exit(0)

    if args.is_carousel and len(images) > 1:
        print(f"🔹 Detected Carousel Mode ({len(images)} slides)")
        child_ids = []
        
        # UPLOAD CHILDREN (SLOWLY)
        for i, img in enumerate(images):
            print(f"   [{i+1}/{len(images)}] Uploading child: {img}")
            cid = upload_single_image(img)
            if cid:
                child_ids.append(cid)
            
            # SLEEP 15s HERE TO PREVENT BURST LIMIT
            print("   ... sleeping 15s to respect API rate limit ...")
            time.sleep(15) 
            
        if not child_ids:
            print("❌ No children created.")
            sys.exit(1)
            
        print("   Linking children to parent container...")
        parent_id = create_carousel_container(child_ids, caption)
        
        if parent_id:
            print(f"✅ Created Parent Carousel Container ID: {parent_id}")
            
            if wait_for_processing(parent_id):
                print("   ⏳ Waiting 60s for container to stabilize before publishing...")
                time.sleep(60) 
                publish_media(parent_id)
    else:
        print("🔹 Single Image Mode")
        cid = upload_single_image(images[0], caption=caption)
        if cid and wait_for_processing(cid):
            publish_media(cid)

if __name__ == "__main__":
    main()
