import os
import random
import argparse
import sys
from collections import defaultdict
from typing import List, Dict, Optional, Tuple

from PIL import Image, ImageFilter, ImageEnhance

# --- 資料讀取與前處理 ---

def build_char_map_from_casia(data_dir: str) -> Dict[str, List[str]]:
    """
    讀取 CASIA 資料集 (以 U+XXXX 命名的圖片)。
    
    Args:
        data_dir (str): CASIA 資料集根目錄。

    Returns:
        Dict[str, List[str]]: 字符對應到的圖片路徑列表。
    """
    print(f"正在索引 CASIA 資料夾: {data_dir}...")
    char_map = defaultdict(list)
    total_files = 0
    
    for root, _, files in os.walk(data_dir):
        for filename in files:
            if filename.startswith("U+") and filename.lower().endswith(('.jpg', '.png', '.jpeg')):
                try:
                    # 解析 Unicode (例如: U+4E00 -> 0x4E00 -> '一')
                    hex_code = filename.split('.')[0].replace("U+", "")
                    char_code = int(hex_code, 16)
                    char = chr(char_code)
                    
                    file_path = os.path.join(root, filename)
                    char_map[char].append(file_path)
                    total_files += 1
                except ValueError:
                    continue
                    
    print(f"索引完成！找到 {len(char_map)} 個獨立字元，共 {total_files} 張圖片。")
    return char_map

def load_company_names(filepath: str) -> List[str]:
    """
    讀取公司名稱列表 CSV/TXT 檔案。
    假設格式為 CSV，且公司名稱位於第 3 欄 (index 2)。
    """
    print(f"正在讀取公司名稱列表: {filepath}...")
    company_names = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                parts = line.split(',')
                # 根據您的資料格式，取第 3 欄
                if len(parts) >= 3 and parts[2]:
                    company_names.append(parts[2].strip())
    except Exception as e:
        print(f"讀取錯誤: {e}")
        return []
        
    print(f"讀取完成！載入 {len(company_names)} 筆有效公司名稱。")
    return company_names

# --- 圖像處理核心邏輯 ---

def _get_char_mask(char: str, char_map: Dict[str, List[str]]) -> Optional[Image.Image]:
    """
    取得單個字元的二值化 Mask。
    包含：隨機選字、適應性二值化、微幅旋轉 (-3~3度)。
    """
    if char not in char_map:
        return None
    
    img_path = random.choice(char_map[char])
    try:
        img_gray = Image.open(img_path).convert('L')
        
        # 適應性二值化 (判斷白底黑字或黑底白字)
        try: 
            bg_pixel_value = img_gray.getpixel((0, 0))
        except IndexError: 
            bg_pixel_value = 255 
            
        if bg_pixel_value > 128: # 白底黑字
            threshold = 230
            mask = img_gray.point(lambda p: 255 if p < threshold else 0, 'L')
        else: # 黑底白字
            threshold = 50 
            mask = img_gray.point(lambda p: 255 if p > threshold else 0, 'L')

        bbox = mask.getbbox()
        if not bbox: return None
        mask_cropped = mask.crop(bbox)
        
        # 微幅旋轉
        angle = random.randint(-3, 3) 
        mask_cropped_rotated = mask_cropped.rotate(angle, resample=Image.BICUBIC, expand=True)
        
        bbox_rotated = mask_cropped_rotated.getbbox()
        if not bbox_rotated: 
            mask_augmented = mask_cropped 
        else:
            mask_augmented = mask_cropped_rotated.crop(bbox_rotated)
        
        return mask_augmented
    
    except Exception:
        return None

def generate_synthetic_image(char_map: Dict[str, List[str]], 
                             background_path: str, 
                             reference_field_bbox: Tuple[int, int, int, int], 
                             company_name: str) -> Tuple[Optional[Image.Image], Optional[str]]:
    """
    生成合成發票圖片。
    
    Args:
        char_map: 字元庫
        background_path: 背景圖片路徑
        reference_field_bbox: 填入文字的目標區域 (xmin, ymin, xmax, ymax)
        company_name: 目標公司名稱字串

    Returns:
        (合成圖片, 標籤文字)
    """
    label = company_name
    selected_char_list = list(label) 
    
    # 檢查缺字
    for char in selected_char_list:
        if char not in char_map: 
            return None, None 

    # 取得所有字元的 Mask
    processed_char_masks = [] 
    for char in selected_char_list:
        mask = _get_char_mask(char, char_map)
        if mask: 
            processed_char_masks.append(mask)
        else: 
            return None, None
            
    if not processed_char_masks: return None, None

    # --- 尺寸標準化邏輯 ---
    # 1. 找出最高高度
    max_h = max(m.height for m in processed_char_masks)
    if max_h == 0: return None, None

    normalized_char_masks = []
    
    for mask in processed_char_masks:
        if mask.height == 0: continue
        
        aspect_ratio = mask.width / mask.height
        
        # 處理扁平字 (如 "一", "二")
        is_flat_char = aspect_ratio > 2.0
        
        if is_flat_char:
            target_width = int(max_h * 0.9)
            new_height = int(target_width / aspect_ratio)
            new_height = max(new_height, int(max_h * 0.15)) 
            
            if target_width == 0: continue
            normalized_char_masks.append(mask.resize((target_width, new_height), Image.LANCZOS))
        else:
            new_height = max_h
            new_width = int(new_height * aspect_ratio)
            
            if new_width == 0: continue
            normalized_char_masks.append(mask.resize((new_width, new_height), Image.LANCZOS))
            
    processed_char_masks = normalized_char_masks
    if not processed_char_masks: return None, None

    # --- 計算整體縮放與排版 ---
    spacings = [random.randint(2, 10) for _ in range(len(processed_char_masks) - 1)]
    original_total_width = sum(m.width for m in processed_char_masks) + sum(spacings)
    if original_total_width == 0: return None, None
    
    field_width = reference_field_bbox[2] - reference_field_bbox[0]
    field_height = reference_field_bbox[3] - reference_field_bbox[1]
    
    # 計算縮放比例 (Scale Factor)
    target_height_px = (field_height - 6) * random.uniform(0.75, 0.90)
    scale_factor = target_height_px / max_h
    
    expected_width = original_total_width * scale_factor
    if expected_width > (field_width - 10):
        scale_factor = (field_width - 10) / original_total_width
    
    scale_factor = min(2.5, scale_factor)

    # 執行縮放
    scaled_char_data = []
    for mask in processed_char_masks:
        nw = int(mask.width * scale_factor)
        nh = int(mask.height * scale_factor)
        if nw == 0 or nh == 0: continue
        scaled_char_data.append((mask.resize((nw, nh), Image.LANCZOS), nw, nh))
        
    if not scaled_char_data: return None, None

    # --- 背景合成 ---
    try:
        base_canvas = Image.open(background_path).convert('RGB')
        # 隨機背景色偏 (Augmentation)
        if random.random() < 0.85:
            r_tint = random.randint(210, 255)
            g_tint = random.randint(210, 255)
            b_tint = random.randint(210, 255)
            if (r_tint, g_tint, b_tint) == (255, 255, 255): g_tint = 240
            
            color_tint_layer = Image.new('RGB', base_canvas.size, (r_tint, g_tint, b_tint))
            alpha_blend = random.uniform(0.7, 0.9)
            base_canvas = Image.blend(base_canvas, color_tint_layer, alpha=alpha_blend)
    except Exception as e:
        print(f"背景載入失敗: {e}")
        return None, None

    # --- 貼上文字 ---
    total_w_scaled = sum(w for _, w, _ in scaled_char_data) + sum(int(s * scale_factor) for s in spacings)
    
    min_x_offset = 5
    max_x_offset = max(min_x_offset, field_width - total_w_scaled - 5)
    
    # 決定起始 X 座標
    paste_x = reference_field_bbox[0] + (random.randint(min_x_offset, max_x_offset) if min_x_offset < max_x_offset else min_x_offset)
    
    field_center_y = reference_field_bbox[1] + (field_height // 2)
    global_y_jitter = random.randint(-2, 2)

    # 決定文字顏色
    color_choice = random.choice(['black', 'blue'])
    if color_choice == 'black': 
        shade = random.randint(20, 80)
        text_color = (shade, shade, shade)
    else: 
        text_color = (random.randint(10, 50), random.randint(20, 60), random.randint(90, 180))

    canvas = base_canvas.copy()
    curr_x = paste_x
    real_min_y = canvas.height
    real_max_y = 0
    
    for i, (mask, w, h) in enumerate(scaled_char_data):
        y_to_paste = field_center_y - (h // 2) + global_y_jitter

        real_min_y = min(real_min_y, y_to_paste)
        real_max_y = max(real_max_y, y_to_paste + h)
        
        char_img = Image.new('RGB', (w, h), text_color)
        canvas.paste(char_img, (curr_x, y_to_paste), mask)
        
        curr_x += w
        if i < len(spacings): 
            curr_x += int(spacings[i] * scale_factor)

    # --- 最終裁切與後處理 ---
    x1 = max(0, paste_x - 5)
    y1 = max(0, real_min_y - 5)
    x2 = min(canvas.width, curr_x + 5)
    y2 = min(canvas.height, real_max_y + 5)
    
    cropped_image = canvas.crop((x1, y1, x2, y2))
    
    # 模糊
    if random.random() < 0.3: 
        cropped_image = cropped_image.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.2, 0.8)))
    
    # 亮度對比
    if random.random() < 0.3:
        enhancer = ImageEnhance.Brightness(cropped_image)
        cropped_image = enhancer.enhance(random.uniform(0.8, 1.2))
        enhancer = ImageEnhance.Contrast(cropped_image)
        cropped_image = enhancer.enhance(random.uniform(0.8, 1.2))
        
    return cropped_image, label

# --- 主程式進入點 ---

def main():
    parser = argparse.ArgumentParser(description="合成公司名稱資料生成器 (基於 CASIA 手寫資料集)")
    
    parser.add_argument("--casia_dir", required=True, help="CASIA 資料集根目錄 (包含 U+XXXX 圖片)")
    parser.add_argument("--bg_image", required=True, help="發票背景圖片路徑 (.jpg/.png)")
    parser.add_argument("--company_list", required=True, help="公司名稱列表 CSV/TXT 檔案路徑")
    parser.add_argument("--output_dir", default="synthetic_output", help="輸出資料夾 (預設: synthetic_output)")
    
    # BBox 參數 (選填，預設為您程式碼中的值)
    parser.add_argument("--bbox", type=int, nargs=4, default=[147, 58, 628, 101], 
                        help="填入區域的 BBox: xmin ymin xmax ymax (預設: 147 58 628 101)")

    args = parser.parse_args()

    # 驗證路徑
    if not os.path.exists(args.bg_image):
        print(f"錯誤：找不到背景圖片 {args.bg_image}")
        sys.exit(1)
    if not os.path.exists(args.casia_dir):
        print(f"錯誤：找不到 CASIA 資料夾 {args.casia_dir}")
        sys.exit(1)
    if not os.path.exists(args.company_list):
        print(f"錯誤：找不到公司列表檔案 {args.company_list}")
        sys.exit(1)

    # 建立輸出目錄
    os.makedirs(args.output_dir, exist_ok=True)
    label_file_path = os.path.join(args.output_dir, "labels.txt")

    # 載入資料
    character_map = build_char_map_from_casia(args.casia_dir)
    all_company_names = load_company_names(args.company_list)
    
    if not character_map or not all_company_names:
        print("錯誤：資料載入失敗，請檢查來源檔案。")
        sys.exit(1)

    print(f"\n--- 開始為 {len(all_company_names)} 間公司生成圖片 ---")
    
    generated_count = 0
    reference_bbox = tuple(args.bbox) # 轉為 tuple

    with open(label_file_path, 'w', encoding='utf-8') as label_file:
        for i, company_name in enumerate(all_company_names):
            
            synthetic_image, image_label = generate_synthetic_image(
                character_map, 
                args.bg_image, 
                reference_bbox, 
                company_name
            )
            
            if not synthetic_image:
                if i % 100 == 0: 
                    print(f"跳過: {i}/{len(all_company_names)} (缺字或生成失敗)")
                continue
            
            base_filename = f"comp_{generated_count:06d}.png"
            output_path = os.path.join(args.output_dir, base_filename)
            
            try:
                synthetic_image.save(output_path, "PNG")
                
                # 寫入標籤
                line_content = f"{base_filename}\t{image_label}\n"
                label_file.write(line_content)
                label_file.flush()
                
                generated_count += 1
                
                if generated_count % 50 == 0:
                    print(f"進度: 已生成 {generated_count} 張圖片...")
                    
            except Exception as e:
                print(f"儲存失敗: {e}")

    print(f"\n--- 全部完成 ---")
    print(f"成功生成: {generated_count} 張")
    print(f"輸出位置: {args.output_dir}")
    print(f"標籤檔案: {label_file_path}")

if __name__ == "__main__":
    main()
