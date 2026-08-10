import requests

def get_skin_price(market_hash_name: str):
    url = f"https://steamcommunity.com/market/priceoverview/?appid=730&currency=20&market_hash_name={market_hash_name}"
    resp = requests.get(url)
    return resp.json() if resp.status_code == 200 else None