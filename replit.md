# Video Downloader Application

## Overview

This is a Flask-based web application that allows users to download videos from YouTube and Instagram. The application provides a simple web interface for users to input video URLs and monitor download progress in real-time.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes (July 16, 2025)

- Fixed FFmpeg integration issues in Streamlit version
- Installed system FFmpeg dependency for audio conversion
- Created optimized main_streamlit.py with proper FFmpeg path detection
- Added better error handling for Instagram downloads
- Improved platform-specific format selection (Instagram vs YouTube)
- Added visual FFmpeg status indicator in Streamlit interface
- **NEW**: Created streamlit_improved.py with enhanced features:
  - Fixed MP3 conversion functionality with proper FFmpeg integration
  - Added local file to MP3 conversion capability
  - Removed Instagram functionality (YouTube only)
  - Improved visual design with gradients and modern UI
  - Enhanced error handling and progress tracking
  - Added file upload functionality for local video conversion

## System Architecture

The application follows a traditional Flask web application architecture with the following key components:

- **Flask Web Framework**: Serves as the main application framework
- **SQLAlchemy ORM**: Handles database operations with SQLite as the default database
- **yt-dlp**: Third-party library for video downloading capabilities
- **Bootstrap Frontend**: Provides responsive UI components
- **Threading**: Handles background video downloads

## Key Components

### Backend Components

1. **Flask Application (`app.py`)**
   - Main application setup and configuration
   - Database initialization with SQLAlchemy
   - Session management and security configuration

2. **Database Models (`models.py`)**
   - Single `Download` model to track video download requests
   - Includes status tracking, progress monitoring, and metadata storage

3. **Routes (`routes.py`)**
   - Main web endpoints for UI rendering
   - Download initiation and management
   - Basic URL validation and platform detection

4. **Video Downloader (`downloader.py`)**
   - Background video processing using yt-dlp
   - Progress tracking and status updates
   - File management in downloads directory

### Frontend Components

1. **Templates**
   - `base.html`: Common layout with Bootstrap styling
   - `index.html`: Main download form interface
   - `downloads.html`: Download history and progress tracking

2. **Static Assets**
   - Custom CSS for styling enhancements
   - JavaScript for form validation and UI interactions

## Data Flow

1. User submits video URL through web form
2. Application validates URL and detects platform (YouTube/Instagram)
3. Download record is created in database with 'pending' status
4. Background thread initiates video download using yt-dlp
5. Progress updates are stored in database
6. Downloaded files are saved to local downloads directory
7. User can monitor progress through downloads page

## External Dependencies

### Core Dependencies
- **Flask**: Web framework
- **Flask-SQLAlchemy**: ORM for database operations
- **yt-dlp**: Video downloading library
- **Werkzeug**: WSGI utilities and middleware

### Frontend Dependencies
- **Bootstrap**: CSS framework (loaded via CDN)
- **Font Awesome**: Icon library (loaded via CDN)

### Database
- **SQLite**: Default database (configurable via DATABASE_URL environment variable)
- Database connection includes connection pooling and health checks

## Deployment Strategy

The application is designed for containerized deployment:

1. **Development**: Runs on Flask's built-in development server
2. **Production**: Configured with ProxyFix middleware for reverse proxy deployment
3. **Environment Configuration**: Uses environment variables for sensitive settings
4. **File Storage**: Local file system storage in `downloads/` directory
5. **Database**: SQLite by default, easily configurable to other databases via environment variables

### Key Configuration Points
- Session secret key via `SESSION_SECRET` environment variable
- Database connection via `DATABASE_URL` environment variable
- File downloads stored in local `downloads/` directory
- Application runs on port 5000 by default

The application architecture prioritizes simplicity and ease of deployment while providing essential features for video downloading functionality.