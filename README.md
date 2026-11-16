# Raw Image Converter

A Windows desktop application for batch converting camera RAW images into high-quality JPG or PNG files.

Raw Image Converter currently supports Canon CR3, Fujifilm RAF and Sony ARW files, with local processing powered by [rawpy](https://github.com/letmaik/rawpy) and Pillow.

## Supported RAW formats

| Format | Camera manufacturer |
|---|---|
| CR3 | Canon |
| RAF | Fujifilm |
| ARW | Sony |

RAW compatibility can vary by camera model and the LibRaw version used by rawpy.

## Features

- Batch convert RAW photos to JPG or PNG
- Import individual files, entire folders or drag and drop files
- Adjustable JPEG quality and PNG compression
- Custom filename prefixes
- Automatic duplicate filename protection
- Multi-threaded conversion
- Conversion progress and estimated time remaining
- Cancel an ongoing batch
- Image preview with zoom
- Conversion history and saved settings
- Automatically open the output folder after conversion

## Requirements

- Windows
- Python 3.13
- rawpy
- Pillow
- tkinterdnd2

## Run from source

Clone the repository:

```powershell
git clone https://github.com/TGMats/Raw-Image-Converter.git
cd Raw-Image-Converter
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
pip install rawpy pillow tkinterdnd2
```

Start the application:

```powershell
python main.py
```

## How it works

Select your RAW photos or add a folder, choose JPG or PNG, adjust the output settings and start the conversion. Images are processed locally on your computer.

## Author

**Tomás Matias**
