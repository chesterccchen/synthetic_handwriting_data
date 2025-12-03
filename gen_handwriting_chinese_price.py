import os
import random
import argparse
from collections import defaultdict
from typing import List, Tuple, Dict, Optional, Any

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

# --- 全域配置 (Configuration) ---

# 預設的 Bounding Boxes (針對特定發票模板)
# 格式: (x_min, y_min, x_max, y_max)
DEFAULT_BBOXES = [
    (141, 493, 182, 532), # 億
    (199, 492, 235, 534), # 仟
    (255, 492, 291, 534), # 佰
    (308, 492, 344, 534), # 拾
    (366, 492, 402, 534), # 萬
    (424, 491, 460, 533), # 仟
    (480, 492, 516, 534), # 佰
    (536, 492, 572, 534), # 拾
    (591, 490, 627, 532)  # 元
]

# 靜態單位文字
STATIC_UNITS = ['億', '仟', '佰', '拾', '萬', '仟', '佰', '拾', '元']

# 目標字符集 (大寫數字)
TARGET_CHAR_SET = ['零', '壹', '貳', '參', '肆', '伍', '陸', '柒', '捌', '玖']

def build_char_map(data_dir: str) -> Dict[str, List[str]]:
    """
    建立字元對應表，索引資料夾中的所有圖片路徑。
    
    Args:
        data_dir (str): 手寫字資料集的根目錄。

    Returns:
        Dict[str, List[str]]: 鍵為字元，值為該字元的圖片路徑列表。
    """
    print(f"正在索引資料夾: {data_dir}...")
    char_map = defaultdict(list)
    
    for dirpath, _, filenames in os.walk(data_dir):
        for filename in filenames:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                # 假設檔名格式為 '字_id.png' (例如: 參_0.png)
                char = filename.split('_')[0]
                if char: 
                    file_path = os.path.join(dirpath, filename)
                    char_map[char].append(file_path)
                    
    print(f"索引完成！找到 {len(char_map)} 個獨立字元。")
    print(f"總共 {sum(len(v) for v in char_map.values())} 張圖片。")
    return char_map

def _paste_single_char(canvas: Image.Image, 
                       char_map: Dict[str, List[str]], 
                       char_to_draw: str, 
                       bbox: Tuple[int, int, int, int], 
                       text_color: Tuple[int, int, int]) -> bool:
    """
    (Internal Helper) 將單個字元經過隨機變換後貼到畫布的指定 BBox 中。
    包含：墨水暈開模擬、隨機旋轉、縮放、位置抖動。

    Args:
        canvas (Image.Image): 目標畫布。
        char_map (Dict): 字符對應表。
        char_to_draw (str): 要繪製的字元。
        bbox (Tuple): 目標區域 (xmin, ymin, xmax, ymax)。
        text_color (Tuple): 文字顏色 (R, G, B)。

    Returns:
        bool: 成功貼上返回 True，失敗返回 False。
    """
    try:
        if not char_map[char_to_draw]:
            return False
            
        img_path = random.choice(char_map[char_to_draw])
        img_gray = Image.open(img_path).convert('L')
        
        # 1. 建立遮罩 (二值化)
        mask = img_gray.point(lambda p: 255 if p < 200 else 0, 'L')

        # 2. 模擬墨水暈開 (Dilation)
        if random.random() < 0.2:
            mask = mask.filter(ImageFilter.MaxFilter(3))
        
        # 3. 裁切有效區域
        digit_bbox = mask.getbbox()
        if not digit_bbox:
            return False 
        mask_cropped = mask.crop(digit_bbox)

        # 4. 隨機旋轉 (修正：縮小旋轉角度，讓字看起來更端正)
        angle = random.randint(-6, 6)
        mask_cropped = mask_cropped.rotate(angle, resample=Image.BICUBIC, expand=True)
        
        # 再次裁切旋轉後的空白
        digit_bbox = mask_cropped.getbbox()
        if not digit_bbox: return False
        mask_cropped = mask_cropped.crop(digit_bbox)
        
        # 5. 計算縮放比例
        field_width = bbox[2] - bbox[0]
        field_height = bbox[3] - bbox[1]
        
        target_height_base = field_height * random.uniform(0.7, 0.95)
        scale_factor = target_height_base / mask_cropped.height
        
        # (修正：縮小縮放變異，避免字忽大忽小)
        char_specific_scale = scale_factor * random.uniform(0.9, 1.1)
        
        new_width = int(mask_cropped.width * char_specific_scale)
        new_height = int(mask_cropped.height * char_specific_scale)

        # 邊界檢查：如果太寬則限制寬度
        if new_width > field_width * 1.2:
             scale_factor = (field_width * 1.2) / mask_cropped.width
             new_width = int(mask_cropped.width * scale_factor)
             new_height = int(mask_cropped.height * scale_factor)

        if new_width == 0 or new_height == 0: return False
        
        scaled_mask = mask_cropped.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 6. 定位與抖動 (Jitter)
        # (修正：大幅縮小偏移量，讓字保持在格子中央附近)
        x_center_offset = (field_width - new_width) // 2
        y_center_offset = (field_height - new_height) // 2
        
        x_jitter = random.randint(-field_width // 8, field_width // 8) 
        y_jitter = random.randint(-field_height // 8, field_height // 8)
        
        paste_x = bbox[0] + x_center_offset + x_jitter
        paste_y = bbox[1] + y_center_offset + y_jitter
        
        # 7. 貼上 (使用 RGB 純色圖層 + Mask)
        char_img_rgb = Image.new('RGB', (new_width, new_height), text_color)
        canvas.paste(char_img_rgb, (paste_x, paste_y), scaled_mask)
        
        return True
        
    except Exception as e:
        print(f"處理字元 {char_to_draw} (路徑: {img_path}) 時發生錯誤: {e}")
        return False

def generate_capital_number_image(char_map: Dict[str, List[str]], 
                                  background_path: str, 
                                  target_bboxes: List[Tuple[int, int, int, int]],
                                  static_units: List[str]) -> Tuple[Optional[Image.Image], Optional[str]]:
    """
    生成一張合成的中文大寫數字發票圖片。
    包含：背景色偏、手寫數字填入、隨機刪除線繪製。

    Returns:
        Tuple[Image, str]: (合成圖片物件, 對應的標籤文字)。失敗則回傳 (None, None)。
    """
    label_chars = []
    
    try:
        canvas = Image.open(background_path).convert('RGB')
        
        # --- 背景增強 (Data Augmentation) ---
        # 85% 機率加上隨機色偏，模擬紙張泛黃或不同光源
        if random.random() < 0.85:
            r_tint = random.randint(210, 255)
            g_tint = random.randint(210, 255)
            b_tint = random.randint(210, 255)
            
            # 避免純白
            if (r_tint, g_tint, b_tint) == (255, 255, 255):
                g_tint = 240
            
            color_tint_layer = Image.new('RGB', canvas.size, (r_tint, g_tint, b_tint))
            alpha_blend = random.uniform(0.1, 0.3)
            canvas = Image.blend(canvas, color_tint_layer, alpha=alpha_blend)
            
        draw = ImageDraw.Draw(canvas)
        
    except Exception as e:
        print(f"載入背景圖片 {background_path} 失敗: {e}")
        return None, None
            
    # --- 決定筆跡顏色 ---
    color_choice = random.choice(['black', 'blue'])
    if color_choice == 'black':
        shade = random.randint(20, 80)
        text_color = (shade, shade, shade)
    elif color_choice == 'blue':
        text_color = (random.randint(10, 50), random.randint(20, 60), random.randint(90, 180))
    
    # --- 刪除線屬性 ---
    line_color = text_color 
    line_width = random.randint(2, 4)
    
    # --- 決定數字填寫起始點 ---
    # 權重設計：讓 '仟', '佰', '拾', '元' 有更高機率被選為起始點，以產生前導空格
    indices = list(range(len(target_bboxes)))
    weights = [1, 1, 1, 1, 2, 3, 4, 5, 5] 
    start_index = random.choices(indices, weights=weights, k=1)[0]
    
    line_bboxes = [] # 收集需要畫刪除線的區域
    
    # --- 填入數字與空格 ---
    for i, bbox in enumerate(target_bboxes):
        unit_char = static_units[i]
        
        if i < start_index:
            # Case 1: 空白欄位 (紀錄 BBox 以便稍後畫線)
            label_chars.append(" " + unit_char) 
            line_bboxes.append(bbox)
            
        elif i == start_index:
            # Case 2: 第一個數字
            # 如果是 '元' 欄位，可以是 0；否則首位不可為 0
            if i == len(target_bboxes) - 1:
                current_char_set = TARGET_CHAR_SET # 0~9
            else:
                current_char_set = TARGET_CHAR_SET[1:] # 1~9
            
            char_to_draw = random.choice(current_char_set)
            label_chars.append(char_to_draw + unit_char)
            _paste_single_char(canvas, char_map, char_to_draw, bbox, text_color)

        else: # i > start_index
            # Case 3: 後續數字 (可以是 0)
            char_to_draw = random.choice(TARGET_CHAR_SET)
            label_chars.append(char_to_draw + unit_char)
            _paste_single_char(canvas, char_map, char_to_draw, bbox, text_color)
    
    # --- 繪製手寫波浪刪除線 (Wavy Strikethrough) ---
    if line_bboxes and random.random() < 0.5:
        try:
            ref_bbox = line_bboxes[0]
            field_height = ref_bbox[3] - ref_bbox[1]
            y_center = (ref_bbox[1] + ref_bbox[3]) // 2
            
            x_start = min(b[0] for b in line_bboxes) + random.randint(3, 10)
            x_end = max(b[2] for b in line_bboxes) - random.randint(3, 10)

            points = []
            x = x_start
            base_y = y_center + random.randint(-field_height // 4, field_height // 4)
            points.append((x, base_y))

            while x < x_end:
                x_step = random.randint(30, 70)
                x = min(x + x_step, x_end)
                # 垂直抖動 (Tremor)
                y_tremor = random.randint(-4, 4)
                points.append((x, base_y + y_tremor))
            
            points[-1] = (x_end, base_y + random.randint(-2, 2))
            
            # 使用 PIL 的 line 繪製多點連線
            draw.line(points, fill=line_color, width=line_width)

        except Exception as e:
            print(f"繪製刪除線時發生錯誤: {e}")

    # --- 最終裁切與後製 ---
    final_label = "".join(label_chars)
    
    min_x = min(box[0] for box in target_bboxes)
    min_y = min(box[1] for box in target_bboxes)
    max_y = max(box[3] for box in target_bboxes)
    max_x_override = 650 
    
    padding = 5 
    final_crop_box = (
        max(0, min_x - padding),
        max(0, min_y - padding),
        min(canvas.width, max_x_override), 
        min(canvas.height, max_y + padding)
    )
    
    if final_crop_box[0] >= final_crop_box[2] or final_crop_box[1] >= final_crop_box[3]:
        return None, None
        
    cropped_image = canvas.crop(final_crop_box)
    
    # 模糊處理 (Gaussian Blur)
    if random.random() < 0.4:
        cropped_image = cropped_image.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 1.0)))
    
    # 亮度與對比調整
    if random.random() < 0.3:
        enhancer = ImageEnhance.Brightness(cropped_image)
        cropped_image = enhancer.enhance(random.uniform(0.8, 1.2))
        
        enhancer = ImageEnhance.Contrast(cropped_image)
        cropped_image = enhancer.enhance(random.uniform(0.8, 1.2))
            
    return cropped_image, final_label

def main():
    parser = argparse.ArgumentParser(description="合成中文大寫金額 OCR 訓練資料生成器")
    parser.add_argument("--char_dir" , required=True, help="手寫單字圖片資料夾路徑")
    parser.add_argument("--bg_image" , required=True, help="發票背景圖片路徑 (.jpg/.png)")
    parser.add_argument("--output_dir", required=True, help="輸出資料夾路徑")
    parser.add_argument("--count", type=int, default=100, help="要生成的圖片數量")
    args = parser.parse_args()
    args = parser.parse_args()

    # 檢查路徑
    if not os.path.exists(args.bg_image):
        print(f"錯誤：找不到背景圖片 {args.bg_image}")
        return

    # 建立輸出目錄
    os.makedirs(args.output_dir, exist_ok=True)

    # 載入字符集
    char_map = build_char_map(args.char_dir)
    
    # 檢查缺字
    missing_chars = [c for c in TARGET_CHAR_SET if c not in char_map]
    if missing_chars:
        print(f"警告: 資料夾中缺少以下必要字元: {missing_chars}")
        # 可選擇是否 return 終止
    
    if not char_map:
        print("錯誤: 字符索引為空，程式終止。")
        return

    print(f"\n--- 開始生成 {args.count} 張圖片 ---")
    
    label_records = []
    successful_generations = 0
    
    while successful_generations < args.count:
        synthetic_image, image_label = generate_capital_number_image(
            char_map, 
            args.bg_image, 
            DEFAULT_BBOXES,
            STATIC_UNITS
        )
        
        # 簡單過濾：確保有產生有效標籤
        if not synthetic_image or not image_label:
            continue
            
        # 存檔處理
        base_filename = f"{image_label}.png"
        output_path = os.path.join(args.output_dir, base_filename)
        
        # 處理檔名重複
        dup_count = 1
        while os.path.exists(output_path):
            output_path = os.path.join(args.output_dir, f"{image_label}_{dup_count}.png")
            dup_count += 1
            
        synthetic_image.save(output_path, "PNG")
        
        final_filename = os.path.basename(output_path)
        label_records.append(f"{final_filename}\t{image_label}")
        
        successful_generations += 1
        if successful_generations % 10 == 0:
            print(f"進度: [{successful_generations}/{args.count}]")

    # 寫入標籤檔 (Label File)
    label_file_path = os.path.join(args.output_dir, "labels.txt")
    with open(label_file_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(label_records))
    
    print(f"\n--- 全部完成 ---")
    print(f"資料集已儲存至: {args.output_dir}")
    print(f"標註檔案: {label_file_path}")

if __name__ == "__main__":
    main()
