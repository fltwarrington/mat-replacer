from flask import Flask, request, jsonify
from PIL import Image
import requests
import io
import dropbox
import os
import sys

app = Flask(__name__)

# === CONFIGURATION ===
DROPBOX_ACCESS_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN", "PASTE_YOUR_DROPBOX_TOKEN_HERE")
MAT_COLOR_HEX = '#004000'
TOLERANCE = 10
UPLOAD_FOLDER = '/mat-replacer-outputs'
MAX_FILE_SIZE_MB = 3

# === UTILITIES ===
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_pixel_color(image, x, y):
    return image.getpixel((x, y))

def color_close(c1, c2, tolerance):
    return all(abs(a - b) <= tolerance for a, b in zip(c1, c2))

def safe_flood_fill(img, target_color, replacement_color, tolerance):
    width, height = img.size
    pixels = img.load()
    visited = [[False for _ in range(width)] for _ in range(height)]

    stack = []
    for y in range(height):
        for x in range(width):
            if not visited[y][x] and color_close(pixels[x, y][:3], target_color, tolerance):
                stack.append((x, y))
                while stack:
                    cx, cy = stack.pop()
                    if 0 <= cx < width and 0 <= cy < height and not visited[cy][cx]:
                        if color_close(pixels[cx, cy][:3], target_color, tolerance):
                            pixels[cx, cy] = replacement_color + (255,)
                            visited[cy][cx] = True
                            stack.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])
    return img

def upload_to_dropbox(file_bytes, filename):
    dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
    path = f"{UPLOAD_FOLDER}/{filename}"
    dbx.files_upload(file_bytes.getvalue(), path, mode=dropbox.files.WriteMode.overwrite)
    shared_link = dbx.sharing_create_shared_link_with_settings(path)
    return shared_link.url.replace('?dl=0', '?raw=1')

# === ROUTES ===
@app.route('/replace-mat', methods=['POST'])
def replace_mat():
    file = request.files.get('image')
    image_url = request.form.get('image_url')
    x = request.form.get('x')
    y = request.form.get('y')

    if file:
        image_data = file.read()
    elif image_url:
        response = requests.get(image_url)
        image_data = response.content
    else:
        return jsonify({'error': 'No image provided'}), 400

    # Check file size limit
    if len(image_data) > MAX_FILE_SIZE_MB * 1024 * 1024:
        return jsonify({'error': f'Image file exceeds {MAX_FILE_SIZE_MB}MB limit'}), 400

    image = Image.open(io.BytesIO(image_data)).convert('RGBA')
    width, height = image.size
    sample_x = int(x) if x else width // 2
    sample_y = int(y) if y else height // 2

    try:
        sampled_color = get_pixel_color(image, sample_x, sample_y)[:3]
    except IndexError:
        return jsonify({'error': 'Sample coordinates out of image bounds'}), 400

    mat_color = hex_to_rgb(MAT_COLOR_HEX)
    result = safe_flood_fill(image.copy(), mat_color, sampled_color, TOLERANCE)
    output_bytes = io.BytesIO()
    result.save(output_bytes, format='PNG')
    output_bytes.seek(0)

    file_url = upload_to_dropbox(output_bytes, f'mat_replaced_{sample_x}_{sample_y}.png')
    return jsonify({'url': file_url})

# === MAIN ===
if __name__ == '__main__':
    app.run(debug=True)
