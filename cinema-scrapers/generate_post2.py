def ask_gemini_to_place_stickers(bg_image: Image.Image, stickers: list[Image.Image]):
    """
    V64: Free-Canvas Layout.
    We ask Gemini for precise X/Y coordinates (0-100), Scale, and Rotation.
    """
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        # Fallback: Random scatter if API fails
        return [{
            "sticker_index": i, 
            "x": random.randint(10, 90), 
            "y": random.randint(10, 90), 
            "scale": 1.0, 
            "rotation": 0
        } for i in range(len(stickers))]

    print("🧠 (2/2) Gemini Art Director: Free-form layout...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Resize for API efficiency
        small_bg = bg_image.resize((512, 640))
        small_stickers = [s.resize((256, int(256*s.height/s.width))) for s in stickers]
        
        prompt = """
        You are an avant-garde poster designer. 
        I have 1 Background and several Transparent Cutouts (Sticker 0, Sticker 1...).
        
        Place these stickers on a canvas (0-100 X, 0-100 Y) to create a dynamic, 'Punk Zine' composition.
        
        Constraints:
        1. CENTER DANGER ZONE: The area x=30-70, y=30-70 contains Title Text. Keep important faces out of this box.
        2. CREATIVITY: You can cluster items, overlap them, or push them off the edge.
        3. SIZE: Make important characters BIG (scale 1.2+). Make textures small.
        
        Return JSON: 
        {
          "layout": [
            {
              "sticker_index": 0, 
              "x": 85, 
              "y": 80, 
              "scale": 1.5, 
              "rotation": -15 
            },
            ...
          ]
        }
        """
        
        contents = [prompt, small_bg]
        contents.extend(small_stickers)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash', contents=contents
        )
        
        clean_json = re.search(r'\{.*\}', response.text, re.DOTALL)
        if clean_json:
            data = json.loads(clean_json.group(0))
            return data.get("layout", [])
            
    except Exception as e:
        print(f"⚠️ Gemini Placement failed: {e}")
    
    return []
