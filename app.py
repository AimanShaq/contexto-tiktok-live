import asyncio
import json
import os
from typing import Set
from aiohttp import web, WSMsgType
from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    ConnectEvent, CommentEvent, GiftEvent, LikeEvent,
    FollowEvent, ShareEvent, JoinEvent, DisconnectEvent
)

# Store connected WebSocket clients
websocket_clients: Set[web.WebSocketResponse] = set()

# TikTok client instance
tiktok_client = None


async def broadcast_to_clients(event_data: dict):
    """Send event data to all connected WebSocket clients"""
    if not websocket_clients:
        return
    
    # Remove disconnected clients
    disconnected = set()
    for ws in websocket_clients:
        try:
            await ws.send_json(event_data)
        except Exception:
            disconnected.add(ws)
    
    websocket_clients.difference_update(disconnected)


async def on_connect(event: ConnectEvent):
    """Handle TikTok connection event"""
    print(f"✅ Connected to @{event.unique_id}")
    await broadcast_to_clients({
        'type': 'system',
        'message': f'Connected to @{event.unique_id}',
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
    """Handle comment events"""
    try:
        # Get profile picture URL from avatar object
        avatar_url = None
        if hasattr(event.user, 'avatar'):
            avatar = event.user.avatar
            if hasattr(avatar, 'url_list') and avatar.url_list:
                avatar_url = avatar.url_list[0]
        
        # Fallback to avatar_thumb if avatar not available
        if not avatar_url and hasattr(event.user, 'avatar_thumb'):
            if isinstance(event.user.avatar_thumb, dict) and 'url_list' in event.user.avatar_thumb:
                urls = event.user.avatar_thumb['url_list']
                if urls:
                    avatar_url = urls[0]
        
        print(f"💬 {event.user.nickname}: {event.comment}")
        await broadcast_to_clients({
            'type': 'comment',
            'user': event.user.nickname,
            'user_id': event.user.unique_id,
            'message': event.comment,
            'avatar_url': avatar_url,
            'timestamp': asyncio.get_event_loop().time()
        })
    except Exception as e:
        print(f"Error in on_comment: {e}")


async def on_gift(event: GiftEvent):
    """Handle gift events"""
    try:
        # Try different attribute paths for gift name
        gift_name = getattr(event.gift, 'name', None) or \
                    getattr(getattr(event.gift, 'info', None), 'name', 'Unknown Gift') or \
                    'Unknown Gift'
        
        # Get profile picture
        avatar_url = getattr(getattr(event.user, 'avatar', None), 'url_list', [None])[0] if hasattr(event.user, 'avatar') else None
        if not avatar_url:
            avatar_url = getattr(event.user, 'avatar_thumb', {}).get('url_list', [None])[0]
        
        # Check if gift is repeatable
        is_repeatable = getattr(event.gift, 'streakable', False)
        is_streaking = getattr(event, 'streaking', True)
        repeat_count = getattr(event, 'repeat_count', 1)
        
        # Only send when streak ends or it's a non-streakable gift
        if is_repeatable and not is_streaking:
            print(f"🎁 {event.user.nickname} sent {repeat_count}x {gift_name}")
            await broadcast_to_clients({
                'type': 'gift',
                'user': event.user.nickname,
                'gift_name': gift_name,
                'count': repeat_count,
                'avatar_url': avatar_url,
                'timestamp': asyncio.get_event_loop().time()
            })
        elif not is_repeatable:
            print(f"🎁 {event.user.nickname} sent {gift_name}")
            await broadcast_to_clients({
                'type': 'gift',
                'user': event.user.nickname,
                'gift_name': gift_name,
                'count': 1,
                'avatar_url': avatar_url,
                'timestamp': asyncio.get_event_loop().time()
            })
    except Exception as e:
        print(f"Error in on_gift: {e}")


async def on_like(event: LikeEvent):
    """Handle like events"""
    try:
        # Try to get total likes, fallback to likes count
        total_likes = getattr(event, 'total_likes', getattr(event, 'likes', 0))
        likes = getattr(event, 'likes', 1)
        
        print(f"❤️ {event.user.nickname} liked ({total_likes} total)")
        await broadcast_to_clients({
            'type': 'like',
            'user': event.user.nickname,
            'likes': likes,
            'total_likes': total_likes,
            'timestamp': asyncio.get_event_loop().time()
        })
    except Exception as e:
        print(f"Error in on_like: {e}")


async def on_follow(event: FollowEvent):
    """Handle follow events"""
    try:
        # Get profile picture
        avatar_url = getattr(getattr(event.user, 'avatar', None), 'url_list', [None])[0] if hasattr(event.user, 'avatar') else None
        if not avatar_url:
            avatar_url = getattr(event.user, 'avatar_thumb', {}).get('url_list', [None])[0]
        
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
    print(f"📤 {event.user.nickname} shared the stream!")
    await broadcast_to_clients({
        'type': 'share',
        'user': event.user.nickname,
        'timestamp': asyncio.get_event_loop().time()
    })


async def on_join(event: JoinEvent):
    """Handle join events"""
    print(f"👋 {event.user.nickname} joined!")
    await broadcast_to_clients({
        'type': 'join',
        'user': event.user.nickname,
        'timestamp': asyncio.get_event_loop().time()
    })


async def websocket_handler(request):
    """Handle WebSocket connections"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    websocket_clients.add(ws)
    print(f"🔌 New WebSocket connection (Total: {len(websocket_clients)})")
    
    # Send welcome message
    await ws.send_json({
        'type': 'system',
        'message': 'Connected to viewer',
        'timestamp': asyncio.get_event_loop().time()
    })
    
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                
                # Handle client messages
                if data.get('action') == 'connect':
                    username = data.get('username', '@isaackogz')
                    await connect_to_tiktok(username)
                elif data.get('action') == 'disconnect':
                    await disconnect_from_tiktok()
                    
            elif msg.type == WSMsgType.ERROR:
                print(f'WebSocket error: {ws.exception()}')
    finally:
        websocket_clients.discard(ws)
        print(f"🔌 WebSocket disconnected (Total: {len(websocket_clients)})")
    
    return ws


async def connect_to_tiktok(username: str):
    """Connect to TikTok livestream"""
    global tiktok_client
    
    try:
        # Disconnect existing client
        if tiktok_client and tiktok_client.connected:
            await tiktok_client.disconnect()
        
        # Send connecting status
        await broadcast_to_clients({
            'type': 'status',
            'status': 'connecting',
            'message': f'Connecting to {username}...',
            'timestamp': asyncio.get_event_loop().time()
        })
        
        # Create new client
        tiktok_client = TikTokLiveClient(unique_id=username)
        
        # Add event listeners
        tiktok_client.add_listener(ConnectEvent, on_connect)
        tiktok_client.add_listener(DisconnectEvent, on_disconnect)
        tiktok_client.add_listener(CommentEvent, on_comment)
        tiktok_client.add_listener(GiftEvent, on_gift)
        tiktok_client.add_listener(LikeEvent, on_like)
        tiktok_client.add_listener(FollowEvent, on_follow)
        tiktok_client.add_listener(ShareEvent, on_share)
        tiktok_client.add_listener(JoinEvent, on_join)
        
        # Check if user is live before connecting
        is_live = await tiktok_client.is_live()
        
        if not is_live:
            error_msg = f'{username} is not currently live'
            await broadcast_to_clients({
                'type': 'error',
                'message': error_msg,
                'timestamp': asyncio.get_event_loop().time()
            })
            return
        
        # Start connection in background
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
    # Don't auto-connect on startup
    print("🚀 Server started. Waiting for manual connection...")
    pass


async def cleanup_background_tasks(app):
    """Cleanup on shutdown"""
    global tiktok_client
    if tiktok_client and tiktok_client.connected:
        await tiktok_client.disconnect()


def main():
    app = web.Application()
    
    # Add routes
    app.router.add_get('/', index_handler)
    app.router.add_get('/static/style.css', css_handler)
    app.router.add_get('/ws', websocket_handler)
    
    # Add startup/shutdown handlers
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    # Run the app
    print("🚀 Starting TikTok Live Viewer on http://localhost:8080")
    web.run_app(app, host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()