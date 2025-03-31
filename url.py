import requests
import json

V1API = "https://api.live.bilibili.com/xlive/web-room/v1/playUrl/playUrl"

class BiliLiveStream:
    @staticmethod
    def get_stream_url(room_id):
        real_room_id = BiliLiveStream.get_real_room_id(room_id)
        if real_room_id == -1:
            return None
        param = {"cid": str(real_room_id), "platform": "web"}
        return BiliLiveStream.v1_handler_quality_url(param)

    @staticmethod
    def v1_handler_quality_url(param):
        result = BiliLiveStream.get_request(V1API, param)
        if result is None:
            return None

        try:
            data = json.loads(result)
        except json.JSONDecodeError:
            return None

        if "data" not in data or "durl" not in data["data"]:
            return None
        
        return data["data"]["durl"][0]["url"]

    @staticmethod
    def get_real_room_id(room_id):
        # 這裡應該實現獲取真實房間 ID 的邏輯
        # 暫時直接返回輸入的 room_id
        return room_id

    @staticmethod
    def get_request(api, param):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://live.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin': 'https://live.bilibili.com'
        }
        try:
            response = requests.get(api, params=param, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            return None

def get_bilibili_live_url(room_id):
    """
    給其他 Python 代碼調用的函數
    輸入: 房間號
    輸出: 直播鏈接 (如果獲取失敗則返回 None)
    """
    return BiliLiveStream.get_stream_url(room_id)

def main():
    import sys
    if len(sys.argv) != 2:
        print("使用方法: python bili_live_stream.py <房間ID>")
        sys.exit(1)
    
    try:
        room_id = int(sys.argv[1])
    except ValueError:
        print("錯誤: 房間ID必須是一個整數")
        sys.exit(1)

    url = get_bilibili_live_url(room_id)
    if url:
        print(url)
    else:
        print("無法獲取直播鏈接")

if __name__ == "__main__":
    main()