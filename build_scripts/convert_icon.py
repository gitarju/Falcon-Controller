from PIL import Image
import os

def convert_png_to_ico(png_path, ico_path):
    print(f"Loading {png_path}...")
    img = Image.open(png_path)
    
    # Standard sizes for Windows ICO files
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    print(f"Saving to {ico_path} with sizes: {sizes}...")
    img.save(ico_path, format='ICO', sizes=sizes)
    print("Icon generated successfully!")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_png = os.path.abspath(os.path.join(script_dir, "..", "assets", "icon.png"))
    dest_ico = os.path.abspath(os.path.join(script_dir, "..", "assets", "icon.ico"))
    
    if os.path.exists(src_png):
        convert_png_to_ico(src_png, dest_ico)
    else:
        print(f"Error: Source image not found at {src_png}")
