
import rawpy

from PIL import Image
from threading import Lock
from pathlib import Path

#benchmarking
#import time



output_path_lock = Lock()

def get_unique_output_path(output_folder, filename, extension):
    """Find and reserve a unique output filename."""

    counter = 0

    with output_path_lock:
        while True:

            if counter == 0:
                output_path = output_folder / f"{filename}.{extension}"
            else:
                output_path = output_folder / f"{filename}_{counter}.{extension}"

            try:
                # Create an empty file to reserve this filename.
                with output_path.open("xb"):
                    pass

                return output_path

            except FileExistsError:
                counter += 1


def convert_cr3(input_path, output_folder, output_format, jpeg_quality=95, png_compression=1, filename_prefix=""):
    """Convert one CR3 file into JPG or PNG."""

    input_path = Path(input_path)
    output_folder = Path(output_folder)

    output_format = output_format.upper()

    if output_format not in ("JPG", "PNG"):
        raise ValueError("Unsupported output format.")

    if output_format == "JPG" and not 50 <= jpeg_quality <= 100:
        raise ValueError("JPEG quality must be between 50 and 100.")

    if output_format == "PNG" and not 0 <= png_compression <= 9:
        raise ValueError("PNG compression must be between 0 and 9.")

    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_folder.mkdir(parents=True, exist_ok=True)

    extension = "jpg" if output_format == "JPG" else "png"

    output_path = get_unique_output_path(
        output_folder,
        f"{filename_prefix}{input_path.stem}",
        extension
    )

    # Read and process the RAW image.
    try:
        # Measure RAW file reading.
        
        #BENCH:
        #read_start = time.perf_counter()

        with rawpy.imread(str(input_path)) as raw:
            #BENCH:
            #read_time = time.perf_counter() - read_start

            # Measure RAW image processing.
            #BENCH:
            #process_start = time.perf_counter()

            rgb_image = raw.postprocess(
                use_camera_wb=True,
                output_bps=8,
                half_size=False,
                demosaic_algorithm=rawpy.DemosaicAlgorithm.PPG
            )

            #BENCH:
            #process_time = time.perf_counter() - process_start

        # Convert to Pillow image.
        image = Image.fromarray(rgb_image)
        
        #BENCH:
        #save_start = time.perf_counter()

        # Save using selected format.
        if output_format == "JPG":
            image.save(
                output_path,
                format="JPEG",
                quality=jpeg_quality
            )
        else:
            image.save(
                output_path,
                format="PNG",
                compress_level=png_compression
            )
            
        #BENCH:
        #save_time = time.perf_counter() - save_start

        # print(
        #     f"{input_path.name} | "
        #     f"Read: {read_time:.2f}s | "
        #     f"Processing: {process_time:.2f}s | "
        #     f"Save: {save_time:.2f}s"
        # )

        return output_path

    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    #return output_path
