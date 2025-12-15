# TikTok Live Viewer 🎥

A beautiful, real-time TikTok Live event viewer with a modern UI. Built with Python 3.12, TikTokLive library, and WebSockets.

## Features ✨

- 📱 Real-time event streaming (comments, gifts, likes, follows, shares)
- 🎨 Modern, gradient-based UI with smooth animations
- 📊 Live statistics tracking
- 🔄 WebSocket-based communication
- 🐳 Fully Dockerized setup
- 🎯 Easy to use - just enter a TikTok username

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
mkdir -p tiktok-live-viewer/templates tiktok-live-viewer/static
cd tiktok-live-viewer

# Create all the files:
# - Dockerfile
# - docker-compose.yml
# - requirements.txt
# - app.py
# - templates/index.html
# - static/style.css
# Copy the contents from the artifacts above
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

1. Enter a TikTok username in the input field (e.g., `@isaackogz`)
2. Click "Connect" or press Enter
3. Watch live events stream in real-time!

## Event Types 🎭

The viewer displays the following events:

- 💬 **Comments**: User messages in the chat
- 🎁 **Gifts**: Virtual gifts sent to the streamer
- ❤️ **Likes**: Likes given to the stream
- 👤 **Follows**: New followers
- 📤 **Shares**: Stream shares
- 👋 **Joins**: Users joining the stream
- ℹ️ **System**: Connection status messages

## Environment Variables 🔧

You can customize the default TikTok username by modifying the `docker-compose.yml`:

```yaml
environment:
  - TIKTOK_USERNAME=@your_username_here
```

## Development 🛠️

### Run without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

### Modify the UI

Edit `templates/index.html` to customize the appearance. The container has volume mounts, so changes will reflect immediately.

## Technical Details 🔬

- **Backend**: Python 3.12 with aiohttp and TikTokLive
- **Frontend**: Vanilla JavaScript with WebSocket API
- **Styling**: Modern CSS with gradients and animations
- **Architecture**: WebSocket-based real-time communication

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

### Can't connect to TikTok stream

- Ensure the username is correct and the user is currently live
- Check if the user's stream is public
- TikTok may have rate limits - try again after a few minutes

### WebSocket connection fails

- Check if port 8080 is available
- Ensure your firewall allows connections on port 8080

## Stopping the Application 🛑

```bash
# Stop the container
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## License 📄

This project uses the TikTokLive library which is MIT licensed.

## Credits 🙏

- [TikTokLive](https://github.com/isaackogan/TikTokLive) by Isaac Kogan
- Built with ❤️ using Python and modern web technologies

## Disclaimer ⚠️

This is an unofficial project and is not affiliated with TikTok. Use responsibly and respect TikTok's terms of service.