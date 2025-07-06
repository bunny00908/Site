import re
import requests
from aiogram import Bot, Dispatcher, types, executor

API_TOKEN = '7390503914:AAFNopMlX6iNHO2HTWNYpLLzE_DfF8h4uQ4'   # <--- PUT YOUR BOT TOKEN HERE

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

def clean_url(url):
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    url = url.replace("http://", "https://")
    if url.endswith("/"):
        url = url[:-1]
    return url

def get_base_url(url):
    m = re.match(r"https://[^/]+", url)
    return m.group(0) if m else url

def get_products_list(base_url):
    try:
        r = requests.get(f"{base_url}/products.json", timeout=10)
        if r.status_code == 200 and 'products' in r.json():
            return r.json()['products']
    except:
        pass
    return []

def get_cheapest_product(products):
    cheapest = None
    product = None
    for p in products:
        for v in p['variants']:
            if (cheapest is None) or (float(v['price']) < float(cheapest['price'])):
                cheapest = v
                product = p
    return product, cheapest

def get_product_from_url(url):
    try:
        if "/products/" in url:
            base_url = get_base_url(url)
            handle = url.split("/products/")[1].split("/")[0].split("?")[0]
            api_url = f"{base_url}/products/{handle}.json"
            r = requests.get(api_url, timeout=10)
            if r.status_code == 200 and 'product' in r.json():
                prod = r.json()['product']
                v = min(prod['variants'], key=lambda v: float(v['price']))
                return prod, v
    except:
        pass
    return None, None

def check_shipping_to_india(base_url, variant_id):
    session = requests.Session()
    cart_url = f"{base_url}/cart/add.js"
    cart_data = {"id": variant_id, "quantity": 1}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        session.post(cart_url, data=cart_data, headers=headers, timeout=10)
        shipping_url = f"{base_url}/cart/shipping_rates.json"
        shipping_payload = {
            "shipping_address[zip]": "560001",
            "shipping_address[country]": "India",
            "shipping_address[province]": "Karnataka"
        }
        resp = session.get(shipping_url, params=shipping_payload, timeout=10)
        if resp.status_code == 200 and 'shipping_rates' in resp.json():
            rates = resp.json()['shipping_rates']
            if rates:
                cheapest = min(rates, key=lambda r: float(r['price']))
                rupee_price = float(cheapest['price']) / 100
                return f"🟢 Ships to India (Karnataka): {cheapest['name']} (${rupee_price:.2f})"
            else:
                return "🔴 Does NOT ship to India."
    except:
        pass
    return "🔴 Does NOT ship to India."

def format_output(product, variant, url, shipping_msg):
    return (
        "┏━━━━━━━⍟\n"
        "┃Cheapest Product\n"
        "┗━━━━━━━━━━━⊛\n"
        f"⊙ Product Variant: {variant['title']}\n"
        f"⊙ Product Name: {product['title']}\n"
        f"⊙ Product Price: ${variant['price']}\n"
        f"⊙ Product ID: {variant['id']}\n"
        f"⊙ Shippable: {'✅' if variant['requires_shipping'] else '❌'}\n"
        f"⊙ Taxable: {'✅' if variant['taxable'] else '❌'}\n"
        f"⊙ Product URL: <code>{url}</code>\n"
        f"{shipping_msg}\n"
    )

def fetch_cheapest_from_any_link(link):
    url = clean_url(link)
    product, variant = get_product_from_url(url)
    if product and variant:
        base_url = get_base_url(url)
        shipping_msg = check_shipping_to_india(base_url, variant['id'])
        return format_output(product, variant, url, shipping_msg)
    base_url = get_base_url(url)
    products = get_products_list(base_url)
    if products:
        product, variant = get_cheapest_product(products)
        product_url = f"{base_url}/products/{product['handle']}"
        shipping_msg = check_shipping_to_india(base_url, variant['id'])
        return format_output(product, variant, product_url, shipping_msg)
    return "Failed to fetch products. ❌"

# ---- Telegram Handler ----

@dp.message_handler(lambda message: re.match(r'https?://[^\s]+', message.text))
async def handle_shopify_links(message: types.Message):
    links = re.findall(r'(https?://[^\s]+)', message.text)
    if not links:
        await message.reply("Send any Shopify store/product/collection URL(s)!")
        return
    results = []
    for link in links[:50]:  # Max 50 per message!
        try:
            result = fetch_cheapest_from_any_link(link)
        except Exception as e:
            result = f"{link}\nError: {str(e)}"
        results.append(result)
    reply_text = "\n\n".join(results)
    await message.reply(reply_text[:4096])  # Telegram limit

if __name__ == "__main__":
    print("Bot started!")
    executor.start_polling(dp, skip_updates=True)
