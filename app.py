async def process_guess_queue():
    """Background worker to process queued guesses"""
    while True:
        try:
            # Get guess from queue
            guess_data = await api_queue.get()
            
            if guess_data is None:  # Shutdown signal
                break
            
            event, word, avatar_url = guess_data
            
            # Fetch from Contexto API
            print(f"🎯 Processing guess '{word}' from {event.user.nickname}")
            result = await fetch_contexto_api(game_state['game_number'], word)
            
            if not result:
                print(f"❌ Failed to get valid response for '{word}'")
                api_queue.task_done()
                continue
            
            distance = result['distance']
            
            # Show popup notification with distance and color
            await broadcast_to_clients({
                'type': 'guess_notification',
                'user': event.user.nickname,
                'word': word,
                'distance': distance,
                'avatar_url': avatar_url,
                'timestamp': asyncio.get_event_loop().time()
            })
            
            # Add to guessed words
            game_state['guessed_words'].add(word)
            
            # Store guess
            game_state['guesses'][word] = {
                'distance': distance,
                'user': event.user.nickname,
                'user_id': event.user.unique_id,
                'avatar_url': avatar_url
            }
            
            print(f"📊 {event.user.nickname} guessed '{word}' - Distance: {distance}")
            
            # Check for winner
            if distance == 0:
                print(f"🎉 WINNER! {event.user.nickname} guessed '{word}'!")
                
                # Get top 3 guesses
                sorted_guesses = sorted(
                    game_state['guesses'].items(),
                    key=lambda x: x[1]['distance']
                )[:3]
                
                leaderboard = [
                    {
                        'word': w,
                        'user': data['user'],
                        'distance': data['distance'],
                        'avatar_url': data['avatar_url']
                    }
                    for w, data in sorted_guesses
                ]
                
                await broadcast_to_clients({
                    'type': 'winner',
                    'word': word,
                    'user': event.user.nickname,
                    'avatar_url': avatar_url,
                    'leaderboard': leaderboard,
                    'timestamp': asyncio.get_event_loop().time()
                })
                
                # Start new game after 10 seconds
                await asyncio.sleep(10)
                game_no = init_new_game()
                await broadcast_to_clients({
                    'type': 'game_start',
                    'game_number': game_no,
                    'timestamp': asyncio.get_event_loop().time()
                })
                
            else:
                # Broadcast guess update
                await broadcast_to_clients({
                    'type': 'guess_update',
                    'guesses': game_state['guesses'],
                    'timestamp': asyncio.get_event_loop().time()
                })
            
            api_queue.task_done()
            
        except Exception as e:
            print(f"Error in process_guess_queue: {e}")
            api_queue.task_done()import asyncio
import json
import os
import re
from typing import Set, Dict, Optional
from aiohttp import web, WSMsgType, ClientSession
from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    ConnectEvent, CommentEvent, GiftEvent,
    FollowEvent, ShareEvent, DisconnectEvent
)
import random
import hashlib
from pathlib import Path
import time

# Store connected WebSocket clients
websocket_clients: Set[web.WebSocketResponse] = set()

# TikTok client instance
tiktok_client = None

# Game state
game_state = {
    'game_number': None,
    'guesses': {},  # word -> {distance, user, nickname, avatar_url}
    'guessed_words': set()
}

# Avatar cache
avatar_cache: Dict[str, str] = {}  # user_id -> base64_avatar
AVATAR_CACHE_DIR = Path("/tmp/tiktok_avatars")
MAX_AVATAR_CACHE = 50

# API rate limiting
api_queue = asyncio.Queue()
api_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
last_request_time = 0
MIN_REQUEST_INTERVAL = 0.1  # 100ms between requests


def init_new_game():
    """Initialize a new game"""
    game_state['game_number'] = random.randint(1, 1184)
    game_state['guesses'] = {}
    game_state['guessed_words'] = set()
    print(f"🎮 New game started! Game #{game_state['game_number']}")
    return game_state['game_number']


def init_avatar_cache():
    """Initialize avatar cache directory"""
    AVATAR_CACHE_DIR.mkdir(exist_ok=True)
    print(f"📁 Avatar cache initialized at {AVATAR_CACHE_DIR}")


def cleanup_avatar_cache():
    """Clean up avatar cache on shutdown"""
    if AVATAR_CACHE_DIR.exists():
        for file in AVATAR_CACHE_DIR.glob("*.txt"):
            file.unlink()
        print("🗑️ Avatar cache cleaned up")


def get_user_hash(user_id: str) -> str:
    """Get hash for user ID"""
    return hashlib.md5(user_id.encode()).hexdigest()[:16]


async def get_cached_avatar(user_id: str, fetch_func) -> Optional[str]:
    """Get avatar from cache or fetch and cache it"""
    user_hash = get_user_hash(user_id)
    
    # Check memory cache first
    if user_id in avatar_cache:
        return avatar_cache[user_id]
    
    # Check file cache
    cache_file = AVATAR_CACHE_DIR / f"{user_hash}.txt"
    if cache_file.exists():
        try:
            avatar_url = cache_file.read_text()
            avatar_cache[user_id] = avatar_url
            return avatar_url
        except Exception as e:
            print(f"Error reading cache for {user_id}: {e}")
    
    # Fetch new avatar
    try:
        avatar_url = await fetch_func()
        if avatar_url:
            # Manage cache size
            if len(avatar_cache) >= MAX_AVATAR_CACHE:
                # Remove oldest (first) item
                oldest_key = next(iter(avatar_cache))
                old_hash = get_user_hash(oldest_key)
                old_file = AVATAR_CACHE_DIR / f"{old_hash}.txt"
                if old_file.exists():
                    old_file.unlink()
                del avatar_cache[oldest_key]
            
            # Cache new avatar
            avatar_cache[user_id] = avatar_url
            cache_file.write_text(avatar_url)
            return avatar_url
    except Exception as e:
        print(f"Error fetching avatar for {user_id}: {e}")
    
    return None


async def broadcast_to_clients(event_data: dict):
    """Send event data to all connected WebSocket clients"""
    if not websocket_clients:
        return
    
    disconnected = set()
    for ws in websocket_clients:
        try:
            await ws.send_json(event_data)
        except Exception:
            disconnected.add(ws)
    
    websocket_clients.difference_update(disconnected)


async def fetch_contexto_api(game_no: int, word: str):
    """Fetch distance from Contexto API"""
    try:
        url = f"https://api.contexto.me/machado/en/game/{game_no}/{word}"
        async with ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'distance' in data and 'word' in data:
                        return data
                else:
                    print(f"❌ Contexto API returned status {response.status} for word '{word}'")
                    error_text = await response.text()
                    print(f"   Response: {error_text}")
                    return None
        return None
    except asyncio.TimeoutError:
        print(f"⏱️ Contexto API timeout for word '{word}'")
        return None
    except Exception as e:
        print(f"❌ Error fetching Contexto API for '{word}': {type(e).__name__}: {e}")
        return None


async def fetch_contexto_tip(game_no: int, distance: int):
    """Fetch tip from Contexto API"""
    try:
        url = f"https://api.contexto.me/machado/en/tip/{game_no}/{distance}"
        async with ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('word')
                else:
                    print(f"❌ Contexto tip API returned status {response.status}")
                    error_text = await response.text()
                    print(f"   Response: {error_text}")
        return None
    except asyncio.TimeoutError:
        print(f"⏱️ Contexto tip API timeout")
        return None
    except Exception as e:
        print(f"❌ Error fetching Contexto tip: {type(e).__name__}: {e}")
        return None


def clean_word(text: str) -> Optional[str]:
    """Clean word to only contain A-Z letters"""
    # Strip leading/trailing whitespace first
    text = text.strip()

    # Ignore if more than one word
    if len(text.split()) != 1:
        return None

    # Ignore if it contains any numbers
    if any(char.isdigit() for char in text):
        return None

    # Remove symbols and whitespace, keep only letters
    cleaned = re.sub(r'[^A-Za-z]', '', text)
    
    # Return None if too short after cleaning
    if len(cleaned) < 2:
        return None
    
    return cleaned.lower()


async def on_connect(event: ConnectEvent):
    """Handle TikTok connection event"""
    print(f"✅ Connected to @{event.unique_id}")
    
    # Initialize new game on connect
    game_no = init_new_game()
    
    await broadcast_to_clients({
        'type': 'system',
        'message': f'Connected to @{event.unique_id}',
        'timestamp': asyncio.get_event_loop().time()
    })
    
    await broadcast_to_clients({
        'type': 'game_start',
        'game_number': game_no,
        'timestamp': asyncio.get_event_loop().time()
    })


async def on_disconnect(event: DisconnectEvent):
    """Handle TikTok disconnect event"""
    print("❌ Disconnected from TikTok")
    await broadcast_to_clients({
        'type': 'system',
        'message': 'Disconnected from livestream',
        'timestamp': asyncio.get_event_loop().time()
    })


async def on_comment(event: CommentEvent):
    """Handle comment events - main game logic"""
    try:
        # Clean the word
        word = clean_word(event.comment)
        
        # Validate word
        if not word:
            return
        
        # Check if already guessed
        if word in game_state['guessed_words']:
            print(f"⚠️ Word '{word}' already guessed by {event.user.nickname}")
            
            # Get existing guess data
            existing_data = game_state['guesses'].get(word)
            if existing_data:
                # Get profile picture from cache
                async def fetch_avatar():
                    if hasattr(event.user, 'avatar_thumb') and event.user.avatar_thumb:
                        image_bytes = await tiktok_client.web.fetch_image_data(
                            image=event.user.avatar_thumb
                        )
                        if image_bytes:
                            import base64
                            return f"data:image/webp;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
                    return None
                
                avatar_url = await get_cached_avatar(event.user.unique_id, fetch_avatar)
                
                # Send already guessed notification
                await broadcast_to_clients({
                    'type': 'already_guessed',
                    'user': event.user.nickname,
                    'word': word,
                    'distance': existing_data['distance'],
                    'avatar_url': avatar_url,
                    'timestamp': asyncio.get_event_loop().time()
                })
            return
        
        # Get profile picture from cache
        async def fetch_avatar():
            if hasattr(event.user, 'avatar_thumb') and event.user.avatar_thumb:
                image_bytes = await tiktok_client.web.fetch_image_data(
                    image=event.user.avatar_thumb
                )
                if image_bytes:
                    import base64
                    return f"data:image/webp;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
            return None
        
        avatar_url = await get_cached_avatar(event.user.unique_id, fetch_avatar)
        
        # Add to queue for processing (non-blocking)
        await api_queue.put((event, word, avatar_url))
        print(f"📥 Queued guess '{word}' from {event.user.nickname} (Queue size: {api_queue.qsize()})")
        
    except Exception as e:
        print(f"Error in on_comment: {e}")


async def on_gift(event: GiftEvent):
    """Handle gift events - provide hint and auto-guess"""
    try:
        # Only process if gift streak ended
        is_repeatable = getattr(event.gift, 'streakable', False)
        is_streaking = getattr(event, 'streaking', True)
        
        if is_repeatable and is_streaking:
            return
        
        # Get lowest distance
        if not game_state['guesses']:
            print("🎁 Gift received but no guesses yet")
            return
        
        lowest = min(game_state['guesses'].items(), key=lambda x: x[1]['distance'])
        lowest_distance = lowest[1]['distance']
        
        # Calculate hint distance
        hint_distance = max(1, lowest_distance // 2)
        
        print(f"🎁 Gift from {event.user.nickname}! Getting hint for distance {hint_distance}")
        
        # Fetch tip
        tip_word = await fetch_contexto_tip(game_state['game_number'], hint_distance)
        
        if tip_word:
            await broadcast_to_clients({
                'type': 'hint',
                'word': tip_word,
                'distance': hint_distance,
                'gifter': event.user.nickname,
                'timestamp': asyncio.get_event_loop().time()
            })
            print(f"💡 Hint revealed: '{tip_word}' at distance {hint_distance}")
            
            # Auto-guess the hint word for the gifter
            print(f"🎯 Auto-guessing '{tip_word}' for gifter {event.user.nickname}")
            
            # Check if already guessed
            if tip_word not in game_state['guessed_words']:
                # Get profile picture from cache
                async def fetch_avatar():
                    if hasattr(event.user, 'avatar_thumb') and event.user.avatar_thumb:
                        image_bytes = await tiktok_client.web.fetch_image_data(
                            image=event.user.avatar_thumb
                        )
                        if image_bytes:
                            import base64
                            return f"data:image/webp;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
                    return None
                
                avatar_url = await get_cached_avatar(event.user.unique_id, fetch_avatar)
                
                # Add to guessed words
                game_state['guessed_words'].add(tip_word)
                
                # Store guess with hint distance
                game_state['guesses'][tip_word] = {
                    'distance': hint_distance,
                    'user': event.user.nickname,
                    'user_id': event.user.unique_id,
                    'avatar_url': avatar_url
                }
                
                # Broadcast guess update
                await broadcast_to_clients({
                    'type': 'guess_update',
                    'guesses': game_state['guesses'],
                    'timestamp': asyncio.get_event_loop().time()
                })
                
                print(f"✅ '{tip_word}' added to {event.user.nickname}'s guesses")
            else:
                print(f"⚠️ '{tip_word}' already guessed, not adding again")
        
    except Exception as e:
        print(f"Error in on_gift: {e}")


async def on_follow(event: FollowEvent):
    """Handle follow events"""
    try:
        avatar_url = None
        try:
            if hasattr(event.user, 'avatar_thumb') and event.user.avatar_thumb:
                image_bytes = await tiktok_client.web.fetch_image_data(
                    image=event.user.avatar_thumb
                )
                if image_bytes:
                    import base64
                    avatar_url = f"data:image/webp;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        except Exception:
            pass
        
        print(f"👤 {event.user.nickname} followed!")
        await broadcast_to_clients({
            'type': 'follow',
            'user': event.user.nickname,
            'avatar_url': avatar_url,
            'timestamp': asyncio.get_event_loop().time()
        })
    except Exception as e:
        print(f"Error in on_follow: {e}")


async def on_share(event: ShareEvent):
    """Handle share events"""
    try:
        print(f"📤 {event.user.nickname} shared the stream!")
        await broadcast_to_clients({
            'type': 'share',
            'user': event.user.nickname,
            'timestamp': asyncio.get_event_loop().time()
        })
    except Exception as e:
        print(f"Error in on_share: {e}")


async def websocket_handler(request):
    """Handle WebSocket connections"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    websocket_clients.add(ws)
    print(f"🔌 New WebSocket connection (Total: {len(websocket_clients)})")
    
    # Send current game state
    await ws.send_json({
        'type': 'game_state',
        'game_number': game_state['game_number'],
        'guesses': game_state['guesses'],
        'timestamp': asyncio.get_event_loop().time()
    })
    
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                
                if data.get('action') == 'connect':
                    username = data.get('username', '@isaackogz')
                    await connect_to_tiktok(username)
                elif data.get('action') == 'disconnect':
                    await disconnect_from_tiktok()
                elif data.get('action') == 'reset_game':
                    game_no = init_new_game()
                    await broadcast_to_clients({
                        'type': 'game_start',
                        'game_number': game_no,
                        'timestamp': asyncio.get_event_loop().time()
                    })
                elif data.get('action') == 'free_hint':
                    await handle_free_hint()
                    
            elif msg.type == WSMsgType.ERROR:
                print(f'WebSocket error: {ws.exception()}')
    finally:
        websocket_clients.discard(ws)
        print(f"🔌 WebSocket disconnected (Total: {len(websocket_clients)})")
    
    return ws


async def handle_free_hint():
    """Provide a free hint to the game master"""
    try:
        if not game_state['guesses']:
            await broadcast_to_clients({
                'type': 'system',
                'message': 'No guesses yet! Need at least one guess for a hint.',
                'timestamp': asyncio.get_event_loop().time()
            })
            return
        
        # Get lowest distance
        lowest = min(game_state['guesses'].items(), key=lambda x: x[1]['distance'])
        lowest_distance = lowest[1]['distance']
        
        # Calculate hint distance
        hint_distance = max(1, lowest_distance // 2)
        
        print(f"💡 Free hint requested! Getting hint for distance {hint_distance}")
        
        # Fetch tip
        tip_word = await fetch_contexto_tip(game_state['game_number'], hint_distance)
        
        if tip_word:
            await broadcast_to_clients({
                'type': 'hint',
                'word': tip_word,
                'distance': hint_distance,
                'gifter': 'Game Master (Free)',
                'timestamp': asyncio.get_event_loop().time()
            })
            print(f"💡 Free hint revealed: '{tip_word}' at distance {hint_distance}")
        else:
            await broadcast_to_clients({
                'type': 'system',
                'message': 'Failed to get hint from API. Try again!',
                'timestamp': asyncio.get_event_loop().time()
            })
        
    except Exception as e:
        print(f"Error in handle_free_hint: {e}")
        await broadcast_to_clients({
            'type': 'system',
            'message': f'Error getting hint: {str(e)}',
            'timestamp': asyncio.get_event_loop().time()
        })


async def connect_to_tiktok(username: str):
    """Connect to TikTok livestream"""
    global tiktok_client
    
    try:
        if tiktok_client and tiktok_client.connected:
            await tiktok_client.disconnect()
        
        await broadcast_to_clients({
            'type': 'status',
            'status': 'connecting',
            'message': f'Connecting to {username}...',
            'timestamp': asyncio.get_event_loop().time()
        })
        
        tiktok_client = TikTokLiveClient(unique_id=username)
        
        tiktok_client.add_listener(ConnectEvent, on_connect)
        tiktok_client.add_listener(DisconnectEvent, on_disconnect)
        tiktok_client.add_listener(CommentEvent, on_comment)
        tiktok_client.add_listener(GiftEvent, on_gift)
        tiktok_client.add_listener(FollowEvent, on_follow)
        tiktok_client.add_listener(ShareEvent, on_share)
        
        is_live = await tiktok_client.is_live()
        
        if not is_live:
            error_msg = f'{username} is not currently live'
            await broadcast_to_clients({
                'type': 'error',
                'message': error_msg,
                'timestamp': asyncio.get_event_loop().time()
            })
            return
        
        asyncio.create_task(tiktok_client.start())
        
    except Exception as e:
        error_message = f"Error connecting to {username}: {str(e)}"
        print(f"❌ {error_message}")
        await broadcast_to_clients({
            'type': 'error',
            'message': error_message,
            'timestamp': asyncio.get_event_loop().time()
        })


async def disconnect_from_tiktok():
    """Disconnect from TikTok livestream"""
    global tiktok_client
    
    try:
        if tiktok_client and tiktok_client.connected:
            await tiktok_client.disconnect()
            await broadcast_to_clients({
                'type': 'system',
                'message': 'Disconnected from livestream',
                'timestamp': asyncio.get_event_loop().time()
            })
    except Exception as e:
        error_message = f"Error disconnecting: {str(e)}"
        print(f"❌ {error_message}")
        await broadcast_to_clients({
            'type': 'system',
            'message': error_message,
            'timestamp': asyncio.get_event_loop().time()
        })


async def index_handler(request):
    """Serve the main HTML page"""
    with open('templates/index.html', 'r') as f:
        html = f.read()
    return web.Response(text=html, content_type='text/html')


async def css_handler(request):
    """Serve the CSS file"""
    with open('static/style.css', 'r') as f:
        css = f.read()
    return web.Response(text=css, content_type='text/css')


async def start_background_tasks(app):
    """Start background tasks on app startup"""
    print("🚀 Server started. Ready for Contexto game!")
    # Initialize avatar cache and game
    init_avatar_cache()
    init_new_game()
    
    # Start queue processor
    app['queue_processor'] = asyncio.create_task(process_guess_queue())
    print("✅ Guess queue processor started")


async def cleanup_background_tasks(app):
    """Cleanup on shutdown"""
    global tiktok_client
    
    # Stop queue processor
    await api_queue.put(None)  # Shutdown signal
    if 'queue_processor' in app:
        await app['queue_processor']
    print("✅ Guess queue processor stopped")
    
    if tiktok_client and tiktok_client.connected:
        await tiktok_client.disconnect()
    cleanup_avatar_cache()


def main():
    app = web.Application()
    
    app.router.add_get('/', index_handler)
    app.router.add_get('/static/style.css', css_handler)
    app.router.add_get('/ws', websocket_handler)
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    print("🚀 Starting TikTok Live Contexto Game on http://localhost:8080")
    web.run_app(app, host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()