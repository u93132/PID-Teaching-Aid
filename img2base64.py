# -*- coding: cp950 -*-
import base64

def file_to_base64(file_path):
    """
    讀取檔案並回傳 Base64 編碼字串
    """
    try:
        with open(file_path, "rb") as image_file:
            # 讀取二進位數據 -> 編碼為 Base64 -> 轉為 UTF-8 字串
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
    except Exception as e:
        return "Error: " + str(e)

# 使用範例：
# 執行後會直接在螢幕印出字串，複製它即可
if __name__ == "__main__":
    my_b64 = file_to_base64("./image0/hand.png") 
    print("-" * 30)
    print(my_b64)
    print("-" * 30)
