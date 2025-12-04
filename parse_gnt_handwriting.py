import os
import struct
import argparse
from PIL import Image

def decode_tag_code(tag_code):
    """
    將 GNT 的 tag_code (GBK 編碼) 轉換為 Unicode hex string (e.g., U+4E00)
    """
    try:
        if tag_code <= 0x00FF:
            # ASCII / 半形字符
            unicode_codepoint = tag_code
            return f"U+{unicode_codepoint:04X}"
        else:
            # 雙字節 GBK
            gbk_bytes = struct.pack('<H', tag_code)
            char = gbk_bytes.decode('gbk')
            unicode_codepoint = ord(char)
            return f"U+{unicode_codepoint:04X}"
    except Exception as e:
        print(f"  [Warning] Failed to decode GBK tag: {tag_code:04X}. Error: {e}")
        return f"GBK_{tag_code:04X}"

def process_gnt_file(gnt_path, output_root, prefix, image_format='png'):
    """
    讀取單個 .gnt 檔案並將其內容轉換為圖片
    """
    filename = os.path.basename(gnt_path)
    base_name = os.path.splitext(filename)[0]
    
    # 組合資料夾名稱
    if prefix:
        folder_name = f"{prefix}_{base_name}"
    else:
        folder_name = base_name
        
    target_dir = os.path.join(output_root, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    
    print(f"Processing: {filename} -> Output: {folder_name}")
    
    count = 0
    
    with open(gnt_path, 'rb') as f:
        while True:
            # 1. 讀取 Sample Size (4 bytes)
            header = f.read(4)
            if not header: break 
            
            sample_size = struct.unpack('<I', header)[0]
            
            # 2. 讀取資料區塊
            # 小心：有些損毀的檔案可能會導致讀取錯誤
            try:
                data = f.read(sample_size - 4)
            except Exception:
                print("  [Error] Read failed.")
                break
                
            if len(data) != (sample_size - 4):
                print(f"  [Error] File corrupted or unexpected end in {filename}")
                break
                
            # 3. 解析 (Tag Code, Width, Height)
            tag_code, width, height = struct.unpack_from('<HHH', data, 0)
            
            # 4. 像素資料
            pixel_data = data[6:]
            if len(pixel_data) != (width * height):
                continue
                
            # 5. 建立圖片
            img = Image.frombytes('L', (width, height), pixel_data)
            
            # 6. 取得檔名 (Unicode Hex)
            char_hex = decode_tag_code(tag_code)
            
            # 7. 存檔
            save_name = f"{char_hex}.{image_format}"
            save_path = os.path.join(target_dir, save_name)
            
            # 如果同一個字出現多次 (例如手寫多次)，避免覆蓋
            dup_count = 1
            while os.path.exists(save_path):
                save_name = f"{char_hex}_{dup_count}.{image_format}"
                save_path = os.path.join(target_dir, save_name)
                dup_count += 1
                
            img.save(save_path)
            count += 1
            
    print(f"  -> Saved {count} images.")
    return count

def main():
    parser = argparse.ArgumentParser(description="CASIA HWDB .gnt to Image Converter")
    
    parser.add_argument("--source_dir", type=str, required=True, 
                        help="Directory containing .gnt files")
    parser.add_argument("--output_dir", type=str, required=True, 
                        help="Root directory to save output folders")
    parser.add_argument("--prefix", type=str, default="", 
                        help="Prefix to add to output folder names (e.g., Gnt1.2TrainPart2)")
    parser.add_argument("--format", type=str, default="png", choices=['png', 'jpg'],
                        help="Output image format (default: png)")

    args = parser.parse_args()
    
    # 檢查來源
    if not os.path.exists(args.source_dir):
        print(f"Error: Source directory '{args.source_dir}' does not exist.")
        return

    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"=== Start Converting GNT to {args.format.upper()} ===")
    print(f"Source: {args.source_dir}")
    print(f"Target: {args.output_dir}")
    
    total_images = 0
    gnt_files = [f for f in os.listdir(args.source_dir) if f.endswith('.gnt')]
    
    if not gnt_files:
        print("No .gnt files found in source directory.")
        return

    for gnt_file in gnt_files:
        path = os.path.join(args.source_dir, gnt_file)
        try:
            count = process_gnt_file(path, args.output_dir, args.prefix, args.format)
            total_images += count
        except Exception as e:
            print(f"  [Critical Error] Failed processing {gnt_file}: {e}")
            
    print(f"\n=== All Done ===")
    print(f"Total processed files: {len(gnt_files)}")
    print(f"Total extracted images: {total_images}")

if __name__ == "__main__":
    main()