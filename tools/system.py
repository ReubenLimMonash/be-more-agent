# =========================================================================
#  System Tools
#  Time, web search, image capture
# =========================================================================

import datetime
import subprocess
import os
from typing import Optional
import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


def get_time() -> str:
    """
    Get the current time.
    
    Returns:
        Current time as formatted string
    """
    now = datetime.datetime.now()
    return f"The current time is {now.strftime('%I:%M %p')}."


def search_web(query: str) -> str:
    """
    Search the web for information.
    
    Args:
        query: Search query string
        
    Returns:
        Search results or error message
    """
    if not query or len(query.strip()) < 2:
        return "I need a proper search query to find information."
    
    try:
        logger.info(f"Searching web for: {query}")
        
        with DDGS() as ddgs:
            # Try news first
            try:
                results = list(ddgs.news(query, region='us-en', max_results=1))
                if results:
                    r = results[0]
                    title = r.get('title', 'No Title')
                    body = r.get('body', r.get('snippet', 'No Body'))
                    return f"📰 **{title}**\n{body[:300]}..."
            except Exception as e:
                logger.debug(f"News search failed: {e}")
            
            # Fallback to text search
            try:
                results = list(ddgs.text(query, region='us-en', max_results=1))
                if results:
                    r = results[0]
                    title = r.get('title', 'No Title')
                    body = r.get('body', r.get('snippet', 'No Body'))
                    return f"🔍 **{title}**\n{body[:300]}..."
            except Exception as e:
                logger.debug(f"Text search failed: {e}")
        
        return f"I searched for '{query}' but didn't find any results. Try a different search?"
    
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return "I can't reach the internet right now. Try again later?"

# TODO: Maybe one day I'll enable image capture
# def capture_image(image_path: str = "current_image.jpg") -> str:
#     """
#     Capture an image from the camera.
    
#     Args:
#         image_path: Where to save the image
        
#     Returns:
#         Path to captured image or error message
#     """
#     try:
#         logger.info("Capturing image...")
        
#         # Use rpicam-still if available (modern Raspberry Pi)
#         try:
#             subprocess.run([
#                 "rpicam-still", "-t", "500", "-n",
#                 "--width", "640", "--height", "480",
#                 "-o", image_path
#             ], check=True, timeout=5)
            
#             logger.info(f"Image captured: {image_path}")
#             return image_path
        
#         except (FileNotFoundError, subprocess.TimeoutExpired):
#             # Fallback to libcamera-still
#             try:
#                 subprocess.run([
#                     "libcamera-still", "-t", "500", "-n",
#                     "-o", image_path
#                 ], check=True, timeout=5)
                
#                 logger.info(f"Image captured: {image_path}")
#                 return image_path
            
#             except (FileNotFoundError, subprocess.TimeoutExpired):
#                 # Fallback to raspistill (older Pi)
#                 subprocess.run([
#                     "raspistill", "-t", "500", "-n",
#                     "-w", "640", "-h", "480",
#                     "-o", image_path
#                 ], check=True, timeout=5)
                
#                 logger.info(f"Image captured: {image_path}")
#                 return image_path
    
#     except Exception as e:
#         logger.error(f"Camera error: {e}")
#         return f"I couldn't take a picture. Error: {str(e)[:50]}"
