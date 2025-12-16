# TikTok Live Contexto Game 🎮

An interactive word guessing game powered by TikTok LIVE comments! Based on the popular Contexto game, viewers can guess words through live chat, and the app shows how close they are to the secret word.

## Features ✨

- 🎯 **Interactive Word Guessing**: Viewers comment words, app shows distance from target
- 🎨 **Color-Coded Feedback**: Green (close), Orange (medium), Red (far)
- 🏆 **Winner Celebration**: Animated leaderboard for top 3 guesses
- 🎁 **Gift-Powered Hints**: Send gifts to reveal words closer to the target
- 📊 **Live Leaderboard**: Automatically sorted by distance
- 👥 **Social Tracking**: Follow & Share events in sidebar
- 🔄 **Auto-Reset**: New game starts after winner is found
- 💾 **Manual Reset**: Game master can reset anytime

## How It Works 🎲

### Game Flow

1. **Game Starts**: Random game number (1-1184) is selected
2. **Players Guess**: Viewers comment words in TikTok LIVE
3. **API Check**: Each word is checked via Contexto API
4. **Distance Shown**: Lower distance = closer to target word
5. **Winner Found**: Distance 0 = WINNER! 🎉
6. **Leaderboard**: Top 3 guesses displayed for 10 seconds
7. **New Game**: Automatically starts a new round

### Distance Color Guide

- 🟢 **Green** (≤ 499): Very close!
- 🟠 **Orange** (500-1500): Getting warmer
- 🔴 **Red** (> 1500): Far away

### Gift Hints 🎁

When someone sends a gift:
- Takes the lowest distance guess
- Divides by 2 (minimum 1)
- Reveals a word at that distance as a hint

## Prerequisites 📋

- Docker
- Docker Compose

## Project Structure 📁

```
.
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── app.py
├── templates/
│   └── index.html
└── static/
    └── style.css
```

## Setup & Running 🚀

### 1. Create the project structure

```bash
# Create directories
mkdir -p tiktok-live-contexto/templates tiktok-live-contexto/static
cd tiktok-live-contexto

# Create all the files:
# - Dockerfile
# - docker-compose.yml
# - requirements.txt
# - app.py
# - templates/index.html
# - static/style.css
```

### 2. Build and run with Docker Compose

```bash
# Build the Docker image
docker-compose build

# Start the container
docker-compose up
```

### 3. Access the application

Open your browser and navigate to:
```
http://localhost:8080
```

## Usage 💡

### For Game Master

1. Enter TikTok username (e.g., `@isaackogz`)
2. Click **Connect**
3. Game automatically starts with random number
4. Monitor guesses and leaderboard
5. Click **Reset Game** to start fresh round
6. Watch for winner celebration!

### For Viewers

1. Comment single words in TikTok LIVE chat
2. See your guess appear with distance
3. Try to get distance to 0
4. Send gifts to help everyone with hints!

## Game Rules 📜

### Valid Guesses

- ✅ Only letters (A-Z) allowed
- ✅ First sentence of comment is used
- ✅ Each word can only be guessed once
- ✅ Minimum 2 characters
- ❌ Numbers, symbols, emoji removed

### Hint System

- 🎁 Any gift triggers hint
- 💡 Hint word is at half the lowest distance
- 🎯 Helps narrow down the search area

## Technical Details 🔬

### API Integration

**Contexto Game API**:
- Game endpoint: `https://api.contexto.me/machado/en/game/{game_no}/{word}`
- Tip endpoint: `https://api.contexto.me/machado/en/tip/{game_no}/{distance}`
- 2-second timeout per request
- Validates response format

### Profile Pictures

- Fetched using TikTokLive's `web.fetch_image_data()`
- Converted to base64 data URLs
- Cached per user
- Fallback to initials if fetch fails

### Performance

**Optimized for**:
- ⚡ Async API calls (non-blocking)
- 🧠 In-memory game state
- 🎨 Smooth CSS animations
- 📦 Minimal data transfer

**Resource Usage**:
- Memory: ~50-100MB
- CPU: Low (event-driven)
- Network: ~2KB per guess

## UI Layout 🎨

```
┌──────────────┬────────────────────┬──────────────┐
│   Controls   │    Game Board      │  Info & Hints│
│   & Social   │                    │              │
│              │  GAME: #1234       │  How to Play │
│  Connect     │  GUESSES: 15       │              │
│  Disconnect  │                    │  🟢 Close    │
│  Reset Game  │  [type a word]     │  🟠 Medium   │
│              │                    │  🔴 Far      │
│  Follow/     │  ┌──────────────┐  │              │
│  Share       │  │ User1  word  │  │  💡 Hints    │
│  Events      │  │ 🟢        125│  │              │
│              │  ├──────────────┤  │  word1 (50)  │
│  Error Log   │  │ User2  test  │  │  word2 (125) │
│              │  │ 🟠       1024│  │              │
└──────────────┴────────────────────┴──────────────┘
```

## Winner Modal 🏆

When distance reaches 0:
```
┌─────────────────────────────┐
│         🎉 WINNER! 🎉        │
│                             │
│       [Profile Picture]      │
│       Username Here          │
│       "target_word"          │
│                             │
│      🏆 Top 3 Guesses       │
│                             │
│  #1  [pfp]  User1  word  0  │
│  #2  [pfp]  User2  test  125│
│  #3  [pfp]  User3  code  340│
└─────────────────────────────┘
```

Auto-closes after 10 seconds or click **[X]**

## Development 🛠️

### Run without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

### Modify Styling

Edit `static/style.css` to customize:
- Color schemes
- Animations
- Layout spacing
- Font sizes

## Troubleshooting 🔧

### Container won't start

```bash
# Check logs
docker-compose logs -f

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### API Issues

- Contexto API is external and may have rate limits
- Check console for API error messages
- Invalid words return no response (ignored)

### Profile Pictures Not Showing

- Requires active TikTok connection
- Some users may have privacy settings
- Fallback initials always work

### Game Reset Not Working

- Ensure WebSocket is connected
- Check browser console for errors
- Refresh page if needed

## Advanced Features 🎯

### Game Number Selection

Currently random (1-1184). To use specific game:

```python
# In app.py, modify init_new_game():
game_state['game_number'] = 42  # Your game number
```

### Custom Hint Logic

```python
# In on_gift(), modify:
hint_distance = max(1, lowest_distance // 3)  # Divide by 3 instead
```

### Persistent Leaderboard

Add storage to track all-time best guesses across games.

## License 📄

This project uses:
- TikTokLive (MIT License)
- Contexto API (Public)

## Credits 🙏

- [TikTokLive](https://github.com/isaackogan/TikTokLive) by Isaac Kogan
- [Contexto](https://contexto.me/) for the word game concept
- Built with ❤️ using Python and modern web technologies

## Disclaimer ⚠️

This is an unofficial project and is not affiliated with TikTok or Contexto. Use responsibly and respect their terms of service.

---

**Have fun guessing! May the closest word win! 🎉**