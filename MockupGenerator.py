"""
Art Mockup Generator (Enhanced Quality & Color Matching) developed by Etem Uyar(@ieuyar)

This script takes photos from an input folder, crops them to a 24x36 aspect ratio, 
adds a fine art frame and mat, and then uses the Gemini API to generate high-quality,
realistic mockups. It will skip generating mockups that already exist in the output folder.

Setup:
1. Install required libraries:
   pip install pillow requests colorthief

2. Create folders:
   - Create a folder named `your_photos` in the same directory as this script.
   - Place all the photos you want to create mockups for inside `your_photos`.
   - The script will automatically create a `mockup_outputs` folder for the results.

3. Get a Gemini API Key:
   - Visit https://makersuite.google.com/ to get your free API key.
   - Paste your key into the API_KEY variable below.
"""
import os
import requests
import base64
import time
from PIL import Image, ImageOps
from io import BytesIO
from colorthief import ColorThief # New import for color extraction

# --- CONFIGURATION ---
# IMPORTANT: Paste your Gemini API key here
API_KEY = "" # YOUR API KEY HERE

# --- Gemini Model ---
# Switched back to the correct model for image generation
GEMINI_MODEL = "gemini-2.5-flash-image-preview" 

# --- Folders ---
INPUT_FOLDER = "Favs"
OUTPUT_FOLDER = "mockup_outputs"

# --- Framing Style ---
# The script now crops photos to a 24x36 (or 36x24) aspect ratio before framing.
FRAME_THICKNESS = 50       # Pixels for the black frame
MAT_THICKNESS = 80         # Pixels for the white border/mat around the photo
FRAME_COLOR = "black"
MAT_COLOR = "white"

# --- Delay Settings (in seconds) ---
# To avoid API rate limits. Increase if you still get errors.
DELAY_BETWEEN_SCENES = 1  # Pause between generating living_room, bedroom, etc. for the SAME photo.
DELAY_BETWEEN_PHOTOS = 1  # Pause after all scenes for one photo are done, before starting the next.
RETRY_DELAY = 5           # Initial wait time if the API says "Too Many Requests".

# --- Mockup Scene Base Prompts (Updated for Etsy Cover Style) ---
BASE_SCENE_PROMPTS = {
    "etsy_cover_mockup": "Place this framed artwork on a plain, minimalist, neutral off-white wall. The scene should be clean and simple, with no other objects or furniture. The lighting should be bright and natural, with dappled sunlight casting soft, artistic shadows from a window across the wall and frame. Ensure ultra-realistic detail and professional photography quality.",
    "living_room": "Place this framed artwork on a wall in a bright, modern living room. The room should be filled with realistic sunlight and soft shadows. The wall behind the artwork should have a subtle, harmonious tone. Ensure ultra-realistic detail, lifelike textures, and professional photography quality.",
    "living_room_v2": "Place this framed artwork on a wall in a bright, cozy modern living room. The room should be filled with realistic sunlight and r shadows. The wall behind the artwork should have a subtle, harmonious tone. Ensure ultra-realistic detail, lifelike textures, and professional photography quality.",
    "bedroom": "Place this framed artwork on the wall above a neatly made bed in a cozy, minimalist bedroom. The lighting should be soft and natural. The wall behind the artwork should have a subtle, harmonious tone. Ensure ultra-realistic detail, lifelike textures, and professional photography quality.",
    "office": "Place this framed artwork on the wall of a clean, professional home office. The scene should have good lighting and look photorealistic. The wall behind the artwork should have a subtle, harmonious tone. Ensure ultra-realistic detail, lifelike textures, and professional photography quality."
}
# ---------------------

def add_frame_and_mat(image_path):
    """
    Crops the image to a 2:3 or 3:2 aspect ratio, then adds a white mat and a black frame.
    """
    try:
        photo = Image.open(image_path).convert("RGB")
        iw, ih = photo.size

        # Determine target aspect ratio (3:2 for landscape, 2:3 for portrait)
        is_landscape = iw > ih
        target_aspect = 3/2 if is_landscape else 2/3
        img_aspect = iw / ih

        # Center-crop the image to the target aspect ratio
        if abs(img_aspect - target_aspect) > 0.01: # Only crop if not already the right ratio
            if img_aspect > target_aspect:  # Image is wider than target, crop width
                new_width = int(target_aspect * ih)
                offset = (iw - new_width) // 2
                cropped_photo = photo.crop((offset, 0, iw - offset, ih))
            else:  # Image is taller than target, crop height
                new_height = int(iw / target_aspect)
                offset = (ih - new_height) // 2
                cropped_photo = photo.crop((0, offset, iw, ih - offset))
        else:
            cropped_photo = photo # Aspect ratio is already correct

        # Add the mat and frame
        matted_photo = ImageOps.expand(cropped_photo, border=MAT_THICKNESS, fill=MAT_COLOR)
        framed_photo = ImageOps.expand(matted_photo, border=FRAME_THICKNESS, fill=FRAME_COLOR)
        return framed_photo
    except Exception as e:
        print(f"❌ Error framing image {os.path.basename(image_path)}: {e}")
        return None

def get_dominant_color_name(image_path):
    """Extracts the dominant color from an image and returns its name."""
    try:
        color_thief = ColorThief(image_path)
        dominant_rgb = color_thief.get_color(quality=10) # quality=10 for faster processing

        # Basic mapping of RGB to common color names (can be expanded)
        r, g, b = dominant_rgb
        if r > 200 and g < 100 and b < 100: return "reddish"
        if g > 200 and r < 100 and b < 100: return "greenish"
        if b > 200 and r < 100 and g < 100: return "bluish"
        if r > 150 and g > 150 and b < 100: return "yellowish"
        if r > 150 and b > 150 and g < 100: return "purplish"
        if g > 150 and b > 150 and r < 100: return "teal"
        if (r + g + b) / 3 < 50: return "dark gray"
        if (r + g + b) / 3 > 200: return "light gray"
        if r > g and r > b: return "warm" if g > 100 else "reddish"
        if g > r and g > b: return "cool green"
        if b > r and b > g: return "cool blue"
        
        # More nuanced checks for warm/cool neutrals
        if r > b * 1.2 and g > b * 1.1: return "warm neutral" # More red/green
        if b > r * 1.2 and b > g * 1.1: return "cool neutral" # More blue

        return "neutral" # Default if no strong hue is detected

    except Exception as e:
        print(f"   ⚠️ Could not extract dominant color for {os.path.basename(image_path)}: {e}")
        return "harmonious" # Fallback if color extraction fails

def generate_mockup_with_gemini(framed_image, scene_prompt, scene_name):
    """Sends the framed image to the Gemini API and returns the mockup image."""
    if not API_KEY:
        print("❌ ERROR: API_KEY is not set. Please get a key from makersuite.google.com and paste it into the script.")
        return None

    print(f"   🤖 Sending to AI for '{scene_name}' mockup...")

    buffered = BytesIO()
    framed_image.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    payload = {
        "contents": [{"parts": [{"text": scene_prompt}, {"inlineData": {"mimeType": "image/png", "data": img_base64}}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
        "safetySettings": [
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    headers = {'Content-Type': 'application/json'}
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=240) # Increased timeout
            response.raise_for_status()
            result = response.json()

            # --- ROBUST ERROR HANDLING TO PREVENT CRASHES ---
            candidate = result.get('candidates', [{}])[0]
            
            # Check if the generation was stopped for safety reasons
            if candidate.get('finishReason') == 'SAFETY':
                print(f"   ❌ Generation failed for '{scene_name}' due to safety filters. Skipping.")
                return None

            content = candidate.get('content')
            if content and 'parts' in content and content['parts']:
                part = content['parts'][0]
                if 'inlineData' in part and 'data' in part['inlineData']:
                    generated_data = part['inlineData']['data']
                    image_data = base64.b64decode(generated_data)
                    return Image.open(BytesIO(image_data))
            
            # If we reach here, the response structure was unexpected
            print(f"   ❌ AI did not return a valid image for '{scene_name}'. The response structure was unexpected. Skipping.")
            print(f"      Response: {result}")
            return None
            
        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = RETRY_DELAY * (2 ** attempt)
                    print(f"   ⚠️ Rate limit hit. Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print(f"   ❌ API rate limit exceeded after {max_retries} attempts. Try again later.")
                    return None
            else:
                print(f"   ❌ API request failed: {e}")
                if e.response:
                    print(f"      Status Code: {e.response.status_code}")
                    print(f"      Response Body: {e.response.text}")
                return None
    return None

def main():
    """Main function to run the mockup generation process."""
    print("--- Starting Art Mockup Generator ---")
    print("--- (Will skip any mockups that have already been generated) ---")

    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ Error: Input folder '{INPUT_FOLDER}' not found. Please create it and add your photos.")
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    image_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

    if not image_files:
        print(f"❌ No images found in '{INPUT_FOLDER}'.")
        return

    print(f"✅ Found {len(image_files)} images to process.")

    for i, filename in enumerate(image_files):
        image_path = os.path.join(INPUT_FOLDER, filename)
        print(f"\nProcessing '{filename}' ({i + 1}/{len(image_files)}):")

        # We only need to frame the image once per input file.
        framed_art = None 

        for j, (scene_name, base_prompt) in enumerate(BASE_SCENE_PROMPTS.items()):
            # --- CHECK IF MOCKUP ALREADY EXISTS ---
            output_filename = f"{os.path.splitext(filename)[0]}_{scene_name}_mockup.jpg"
            save_path = os.path.join(OUTPUT_FOLDER, output_filename)
            
            if os.path.exists(save_path):
                print(f"   ⏭️  Skipping '{scene_name}' for '{filename}' - mockup already exists.")
                continue # Skip to the next scene in the loop

            # --- Generate if it doesn't exist ---
            # Frame the image only if we need to generate the first missing mockup for it
            if not framed_art:
                print("   🖼️  Adding fine art frame and mat...")
                framed_art = add_frame_and_mat(image_path)
                if not framed_art:
                    # If framing failed, break out of this inner loop to go to the next image
                    break 

            mockup_image = generate_mockup_with_gemini(framed_art, base_prompt, scene_name)

            if mockup_image:
                # Save the generated mockup
                mockup_image.convert("RGB").save(save_path, "JPEG", quality=98, subsampling=0)
                print(f"   ✅ Successfully saved mockup to '{save_path}'")
            
            if j < len(BASE_SCENE_PROMPTS) - 1:
                print(f"   ... Waiting {DELAY_BETWEEN_SCENES} seconds before next scene ...")
                time.sleep(DELAY_BETWEEN_SCENES)
        
        if i < len(image_files) - 1:
            print(f"\n--- Waiting {DELAY_BETWEEN_PHOTOS} seconds before processing next image ---")
            time.sleep(DELAY_BETWEEN_PHOTOS)

    print("\n--- ✅ All mockups generated successfully! ---")

if __name__ == "__main__":
    main()

