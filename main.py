from flask import Flask, request, jsonify
from PIL import Image
import requests
import io
import dropbox
import os

app = Flask(__name__)

# === CONFIGURATION ===
DROPBOX_ACCESS_TOKEN = 'sl.u.AFsFt5z-ksGUlJCA2OjQY65wQ4-V_eLJ1MdOMBMHu5MWrxrF5Vw-4_g4cUj1YWYsAaHW16IFzJM64T8PSZf0mEFavIJ7VKttzo5039qYlA7cSOASEhWeQRAJxpr44mA_4zzBU6s9Gm3Di7AqRZZveFOsUX9wGSY32y21HaQmr5TaliH8leX_yv0lewbL0BZSyGWT_MLBH9xGeVoCbxZHKNV3qNdS3jL4PZswGS7Oqdx3pwXoJs1YjkBJGDweHVrnBUV3xw9kYNrrq-oPirrzWSBEUEL4Rs7ydOL1nMUHEhg4W3qsq-ASJAQrH8jIe_gVaZl9pbN4DEEjOTzk1zZi9R1P-48SbkOe0ygPNzy9ksApNjMr7tEuaWiK2Jxhtcup4QtbtM77gSK-W5yyYBALMZ1FiO05axdG7K4Z2VHy0NHNxSooXu7ujCO9NYNSH2INfWfJYqgQ0HW5a-EeNcthZFNPGayCSCsE1Fpnc5K_JpsQ_ebZToo-ngVmd_bVJoLw7IXjsQ0eTyadrwAWdN3WdOQCEgC_QHY_qH1belFuvz357DQJjZ2sKjoABdRjD4RRJR4XmR8Roa_MuI-EPg_u1v1jy7OAEEKxEebRJtONnYvuOm6Mmx6W4xXa_37TieFmmVmDgJ1Z960hHGsTjnERZt43FmxiVbUnIeUBp_aNQ_ShI9ZKa4mCpnw_8Ej5ml_uQjbB0Om5MaF2-30nekfu_79rVtjpd4n74daa-Uuj7XdNbd9hzFrqjKa7FkNY5_D3mVaOA-qXYbs3peWRQgW_f0G1Ssctw0TQPTKKE0jx2R0PlNoSA0Pb-ivwErZjgqTticLwNn2MJ4qloJzctESVrE7BE_5y4pujkibxCL4YmDso31RS-oHFH1YMlbaxKlwEWnf6onOMXHnCv_sx4KuelrrFkX7jnHQDBpMOMVHPDyLgPk6BoctbW17_7rYHoxt7ebT76V11e7lWkGeLSqXHY3shpv-dOJFIm4Gfazpvo9iZw4RqGbFlWTzuJOkkXoOJj_cHW0RBYXc2TBGztD-W9_3gDl1BrnOQve5bKRsW3i0lXRGxPAHvgZwVZJQvBmSzvkVrhBBZEbDMA8sFOgOAibmhD2ovv5vXZYxf243aGvU8feAyXndUbrww9Z7MVpTvditwkDYTDUAAJL-9c3NiURBQo6faK6vQKFQu8ACQvVZhO3qGXpsNPscLXVPZQaYYaVhL5A12uPEH4OQFoLHs5yXkGqtdWkUp82-KzVnVKqSF1_TLDmRihgjYB9O4KIepgRKXJWTo5u-vQIULCoETLNWNBUchAQ7yHagfl8XPakeiH_nAIQHn-tuCUqeZw6f-vnekVFN7DmnfKrO8hZyv7hxb'
MAT_COLOR_HEX = '#004000'
TOLERANCE = 10
UPLOAD_FOLDER = '/mat-replacer-outputs'

# === UTILITIES ===
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_pixel_color(image, x, y):
    return image.getpixel((x, y))

def color_close(c1, c2, tolerance):
    return all(abs(a - b) <= tolerance for a, b in zip(c1, c2))

def flood_fill(img, target_color, replacement_color, tolerance):
    width, height = img.size
    pixels = img.load()
    visited = set()

    for y in range(height):
        for x in range(width):
            if (x, y) in visited:
                continue
            if color_close(pixels[x, y][:3], target_color, tolerance):
                queue = [(x, y)]
                while queue:
                    cx, cy = queue.pop()
                    if (cx, cy) in visited:
                        continue
                    if 0 <= cx < width and 0 <= cy < height and color_close(pixels[cx, cy][:3], target_color, tolerance):
                        pixels[cx, cy] = replacement_color + (255,)
                        visited.add((cx, cy))
                        queue.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])
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
        image = Image.open(file.stream).convert('RGBA')
    elif image_url:
        response = requests.get(image_url)
        image = Image.open(io.BytesIO(response.content)).convert('RGBA')
    else:
        return jsonify({'error': 'No image provided'}), 400

    width, height = image.size
    sample_x = int(x) if x else width // 2
    sample_y = int(y) if y else height // 2

    sampled_color = get_pixel_color(image, sample_x, sample_y)[:3]
    mat_color = hex_to_rgb(MAT_COLOR_HEX)

    result = flood_fill(image.copy(), mat_color, sampled_color, TOLERANCE)
    output_bytes = io.BytesIO()
    result.save(output_bytes, format='PNG')
    output_bytes.seek(0)

    file_url = upload_to_dropbox(output_bytes, f'mat_replaced_{sample_x}_{sample_y}.png')
    return jsonify({'url': file_url})

# === MAIN ===
if __name__ == '__main__':
    app.run(debug=True)
