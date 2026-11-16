from pathlib import Path

import rawpy
from PIL import Image

# Change this to the full path of one of your CR3 photos
input_path = Path(r"C:\Users\tmati\Pictures\cr3_Pics_test\IMG_5164.CR3")

# Test output folder inside the project
output_dir = Path("test_output")
output_dir.mkdir(exist_ok=True)

if not input_path.is_file():
    raise FileNotFoundError(
        f"Could not find the CR3 file: {input_path}"
    )

print(f"Reading: {input_path.name}")

with rawpy.imread(str(input_path)) as raw:
    rgb_image = raw.postprocess(
        use_camera_wb=True,
        output_bps=8,
        half_size=False,
    )

image = Image.fromarray(rgb_image)

png_path = output_dir / f"{input_path.stem}.png"
jpg_path = output_dir / f"{input_path.stem}.jpg"

image.save(png_path, format="PNG")
image.save(jpg_path, format="JPEG", quality=95, optimize=True)

print(f"Image dimensions: {image.width} x {image.height}")
print(f"PNG saved: {png_path.resolve()}")
print(f"JPG saved: {jpg_path.resolve()}")
print("Conversion successful!")