import ccxt
import time
import telebot
import threading

api_key = 'kucoin_api_key'
api_secret = 'kucoin_api_secret'
api_passphrase = 'kucoin_api_passphrase'

kucoin = ccxt.kucoin({
    'apiKey': api_key,
    'secret': api_secret,
    'password': api_passphrase,
    'rateLimit': 2000,
    'enableRateLimit': True,
})

bot_token = 'telegram_bot_token'
bot = telebot.TeleBot(bot_token)

active_pairs = {'BTC/EUR': False, 'ETH/EUR': False}
chat_ids = []

def currentSettings(message):
    global active_pairs
    bot.send_message(message.chat.id, """Текущие настройки:
    BTC/EUR: {}
    ETH/EUR: {}
    """.format(active_pairs['BTC/EUR'], active_pairs['ETH/EUR']))


@bot.message_handler(commands=['on_all'])
def on_all(message):
    global active_pairs
    active_pairs = {'BTC/EUR': True, 'ETH/EUR': True}
    bot.send_message(message.chat.id, "Все пары включены.")
    currentSettings(message)

@bot.message_handler(commands=['off_all'])
def off_all(message):
    global active_pairs
    active_pairs = {'BTC/EUR': False, 'ETH/EUR': False}
    bot.send_message(message.chat.id, "Все пары выключены.")
    currentSettings(message)

@bot.message_handler(commands=['on_btc'])
def on_btc(message):
    global active_pairs
    active_pairs['BTC/EUR'] = True
    bot.send_message(message.chat.id, "Торговля BTC включена.")
    currentSettings(message)

@bot.message_handler(commands=['off_btc'])
def off_btc(message):
    global active_pairs
    active_pairs['BTC/EUR'] = False
    bot.send_message(message.chat.id, "Торговля BTC выключена.")
    currentSettings(message)

@bot.message_handler(commands=['on_eth'])
def on_eth(message):
    global active_pairs
    active_pairs['ETH/EUR'] = True
    bot.send_message(message.chat.id, "Торговля ETH включена.")
    currentSettings(message)

@bot.message_handler(commands=['off_eth'])
def off_eth(message):
    global active_pairs
    active_pairs['ETH/EUR'] = False
    bot.send_message(message.chat.id, "Торговля ETH выключена.")
    currentSettings(message)

@bot.message_handler(content_types=['text'])
def start(message):
    global chat_ids
    if message.chat.id not in chat_ids:
        chat_ids.append(message.chat.id)
        print(f'Added chat id: {message.chat.id}')

    bot.send_message(message.chat.id, """Бот запущен.""")
    bot.send_message(message.chat.id, """Доступные команды:
    /on_all - включить торговлю на всех парах
    /off_all - выключить торговлю на всех парах
    /on_btc - включить торговлю на паре BTC/EUR
    /off_btc - выключить торговлю на паре BTC/EUR
    /on_eth - включить торговлю на паре ETH/EUR
    /off_eth - выключить торговлю на паре ETH/EUR
    """)
    currentSettings(message)

def send_successfull_order_message(message):
    for i in chat_ids:
        bot.send_message(i, f"{message}")

def check_new_closed_orders(api_key, api_secret, last_check_time):
    closed_orders = kucoin.fetch_closed_orders()
    new_closed_orders = []

    for order in closed_orders:
        if order["status"] != "closed":
            order_close_time = order["timestamp"] / 1000  # Convert to seconds
            if order_close_time > last_check_time:
                new_closed_orders.append(order)
        else:
            pass

    return new_closed_orders

def check_completed_orders():
    while True:
        last_check_time = time.time()
        new_closed_orders = check_new_closed_orders(api_key, api_secret, last_check_time)
        last_check_time = time.time()

        try:
            for order in new_closed_orders:                    
                side = order['side']
                pair = order['symbol']
                price = order['price']
                size = order['amount']
                send_successfull_order_message(f"""Ордер был успешно закрыт.
    Пара: {pair}
    Сторона: {side}
    Цена: {price}
    Размер: {size}                    
    """)
        except Exception as e:
            print(f"Failed to check completed orders: {e}")


def get_price_step(pair):
    try:
        market_info = kucoin.load_markets()
        return float(market_info[pair]['info']['priceIncrement'])

    except Exception as e:
        print(f"Failed to fetch price step: {e}")
        return None

def round_price_to_step(price, step):
    price_rounded = round(price / step) * step
    if step == 0.01:
        price_rounded = round(price_rounded, 2)
    return price_rounded

def get_account_balance(currency):
    try:
        balances = kucoin.fetch_balance()
        if(currency not in balances['free']):
            return 0

        return balances['free'][currency]
    except Exception as e:
        print(f"Failed to fetch account balance: {e}")
        return 0

def fetch_order_book(pair):
    try:
        return kucoin.fetch_order_book(pair)
    except Exception as e:
        print(f"Failed to fetch order book: {e}")
        return None

def calculate_order_price(pair, side, threshold):
    order_book = fetch_order_book(pair)
    if not order_book:
        return None

    orders = order_book['bids'] if side == 'buy' else order_book['asks']
    best_price = orders[0][0]
    lowest_sell_price = order_book['asks'][0][0]

    if side == 'buy':
        target_price = lowest_sell_price - best_price
        percent = target_price / lowest_sell_price * 100

        if percent >= threshold * 100:
            target_price = best_price
            print("Best price is already good enough")
        else:
            target_price = lowest_sell_price * (1 - threshold)
            
            bid_prices = [order[0] for order in order_book['bids']]
            target_price = max([price for price in bid_prices if price <= target_price])
            print("Best price is not good enough")


    price_step = get_price_step(pair)
    if not price_step:
        print("Failed to fetch price step")
        return None

    rounded_price = round_price_to_step(target_price, price_step)
    
    return rounded_price
        
def place_order(pair, side, price, size):
    try:
        order = kucoin.create_limit_order(pair, side, size, price)
        print(f"Placed {side} order for {pair} at price {price} with size {size}")
        return order

    except Exception as e:
        print(f"Failed to place order: {e}")
        return None

def cancel_order(order_id):
    try:
        return kucoin.cancel_order(order_id)
    except Exception as e:
        print(f"Failed to cancel order: {e}")

def trade(pair, side, threshold, balance_ratio, eur_balance):
    print(f"Start trading {pair} {side} with threshold {threshold} and balance ratio {balance_ratio}")

    if(eur_balance == 0):
        return print("No EUR balance")

    trade_balance = eur_balance * balance_ratio

    best_price = calculate_order_price(pair, side, threshold)
    if not best_price:
        return

    print(f"trade balance - {trade_balance} EUR")
    print(f"best price - {best_price} EUR")
    
    size = trade_balance / best_price * (1 - 0.002)  # 0.2% fee
    size = round(size, 6)  # Round size to the correct precision

    print(f"Account balance is {eur_balance} EUR")
    print(f"Best price is {best_price} and size is {size}")    

    open_orders = kucoin.fetch_open_orders(pair)
    for order in open_orders:
        cancel_order(order['id'])

    
    placed_order = place_order(pair, side, best_price, size)
    if placed_order:
        print(f"Placed {side} order for {pair} at price {best_price} with size {size}")
        message = f"""
Успешно размещен ордер!
Баланс до операции: {eur_balance} EUR
Пара: {pair}
Сторона: {side}
Цена: {best_price}
Количество: {size}
Баланс после операции: {get_account_balance('EUR')} EUR
"""
        send_successfull_order_message(message)
    
def main():
    while True: 
        for pair in ['BTC/EUR', 'ETH/EUR']:
            open_orders = kucoin.fetch_open_orders(pair)
            for order in open_orders:
                cancel_order(order['id'])
                print(f"Cancelled order {order['id']}")
                send_successfull_order_message(f"Ордер был успешно отменен. ID: {order['id']}")

        balance = get_account_balance('EUR')
        
        btc_trade_procent = 0
        eth_trade_procent = 0

        if(active_pairs['BTC/EUR'] and active_pairs['ETH/EUR']):
            if balance < 500:
                btc_trade_procent = 0.83
                eth_trade_procent = 0.17 
            else:
                btc_trade_procent = 0.5
                eth_trade_procent = 0.5
        
        elif(active_pairs['BTC/EUR']):
            btc_trade_procent = 1
            eth_trade_procent = 0

        elif(active_pairs['ETH/EUR']):
            btc_trade_procent = 0
            eth_trade_procent = 1

        print(f'btc: {btc_trade_procent}, eth: {eth_trade_procent}')

        for pair, threshold, balance_ratio, eur_balance in [('BTC/EUR', 0.02, btc_trade_procent, balance), ('ETH/EUR', 0.02, eth_trade_procent, balance)]:
            if active_pairs[pair]:
                trade(pair, 'buy', threshold, balance_ratio, eur_balance)

        time.sleep(120)

if __name__ == "__main__":
    main_thread = threading.Thread(target=main)
    main_thread.start()
    check_orders_thread = threading.Thread(target=check_completed_orders)
    check_orders_thread.start()
    bot.polling(none_stop=True)