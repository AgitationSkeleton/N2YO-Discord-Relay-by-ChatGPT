import discord
import requests
import json
import logging
import os
from datetime import datetime
from discord.ext import tasks
from dotenv import load_dotenv
import asyncio  # Added for delay

# Load credentials from environment variables
load_dotenv()

# Use environment variables or placeholders for your credentials
TOKEN = 'YOUR_DISCORD_TOKEN'  # Replace with your actual Discord token
CHANNEL_ID = 'YOUR_CHANNEL_ID'  # Replace with your target channel ID
N2YO_API_KEY = 'YOUR_N2YO_API_KEY'  # Replace with your actual N2YO API key
OPENCAGE_API_KEY = 'YOUR_OPENCAGE_API_KEY'  # Replace with your OpenCage API key

# Coordinates and Altitude - Replace these with your own if needed
LAT = 0  # Latitude placeholder
LON = 0  # Longitude placeholder
ALT = 0  # Altitude placeholder

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Track reported satellites
reported_satellites = set()
log_file = "satellite_log.json"

BASE_URL = "https://api.n2yo.com/rest/v1/satellite/"

# Helper Functions
def get_satellites_above(observer_lat, observer_lng, observer_alt, search_radius, category_id):
    url = f"{BASE_URL}above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}/&apiKey={N2YO_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()

        # Track the number of remaining queries
        remaining_calls = response.headers.get('X-RateLimit-Remaining')
        if remaining_calls:
            logger.info(f"Remaining API calls: {remaining_calls}")

        # Debugging: Log the full response
        logger.info(f"API Response: {json.dumps(data, indent=4)}")

        if "above" in data:
            return data["above"], remaining_calls  # Return the satellites and remaining query count
    except Exception as e:
        logger.error(f"Error retrieving satellites above: {e}")
    return [], None

def get_satellite_positions(satid, seconds=2):
    url = f"{BASE_URL}positions/{satid}/{LAT}/{LON}/{ALT}/{seconds}/&apiKey={N2YO_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()

        # Track the number of remaining queries
        remaining_calls = response.headers.get('X-RateLimit-Remaining')
        if remaining_calls:
            logger.info(f"Remaining API calls: {remaining_calls}")

        # Debugging: Log the full response
        logger.info(f"API Response: {json.dumps(data, indent=4)}")

        if "info" in data and "positions" in data:
            sat_info = data['info']
            positions = data['positions']
            return sat_info, positions, remaining_calls
    except Exception as e:
        logger.error(f"Error retrieving satellite positions: {e}")
    return None, None, None

def log_satellite_data(sat_name, data, category="positions"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {"timestamp": timestamp, "sat_name": sat_name, category: data}

    # Append to log file
    try:
        with open(log_file, "a") as file:
            file.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write log: {e}")

# Function to reverse geocode coordinates into a location name
def get_location_from_coords(latitude, longitude):
    try:
        url = f"https://api.opencagedata.com/geocode/v1/json?q={latitude}+{longitude}&key={OPENCAGE_API_KEY}"
        response = requests.get(url)
        data = response.json()
        if data['results']:
            # Get the first result's formatted address
            location = data['results'][0]['formatted']
            return location
    except Exception as e:
        logger.error(f"Error in geocoding coordinates: {e}")
    return None

async def send_to_discord(message, sat_id=None, sat_info=None, positions=None, remaining_calls=None):
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        logger.error("Discord channel not found!")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Add timestamp to message

    embed = discord.Embed(
        title=f"🛰️ Satellite: {sat_info.get('satname', 'Unknown')}",
        description=f"{message}\n{timestamp}",  # Include timestamp in message
        color=discord.Color.blue()
    )

    if sat_id:
        embed.url = f"https://www.n2yo.com/satellite/?s={sat_id}"

    # Add satellite details with safe fallbacks
    embed.add_field(name="🌍 NORAD ID", value=sat_info.get("satid", "N/A"), inline=True)

    # Retrieve position data (assuming positions is a list of position data from API)
    if positions:
        position = positions[0]  # Using the first position data
        sat_lat = position.get('satlatitude', 'N/A')
        sat_lon = position.get('satlongitude', 'N/A')

        position_str = f"📍 Location: Lat: {sat_lat}, Lon: {sat_lon}, Alt: {position.get('sataltitude', 'N/A')} km\n"
        position_str += f"🔄 Azimuth: {position.get('azimuth', 'Not available')}\n"
        position_str += f"📡 Elevation: {position.get('elevation', 'Not available')}"

        # Get relative location using reverse geocoding
        location = get_location_from_coords(sat_lat, sat_lon)
        if location:
            position_str += f"\n📍 Overhead: {location}"

        embed.add_field(name="🛰️ Position Info", value=position_str, inline=False)

    # Add the N2YO Transaction count in the footer
    if sat_info and 'transactionscount' in sat_info:
        embed.set_footer(text=f"N2YO Transactions: {sat_info['transactionscount']}/1000")  # Display transaction count out of 1000

    await channel.send(embed=embed)
    logger.info(f"Sent message for {sat_info.get('satname', 'Unknown')}")

    await asyncio.sleep(2)  # Delay to avoid rate limiting

# Task Loops
@tasks.loop(minutes=10)
async def monitor_satellites():
    # Search radius and category ID parameters
    search_radius = 30  # Search for all satellites above the horizon
    category_id = 0  # 0 means all categories

    satellites, remaining_calls = get_satellites_above(LAT, LON, ALT, search_radius, category_id)
    for sat_info in satellites:
        sat_id = sat_info.get('satid')
        sat_name = sat_info.get('satname')

        # Avoid reporting the same satellite multiple times
        if sat_id in reported_satellites:
            continue

        sat_info, positions, remaining_calls = get_satellite_positions(sat_id)

        if sat_info and positions:
            await send_to_discord("", sat_id, sat_info, positions, remaining_calls)  # Removed message text as requested
            log_satellite_data(sat_info['satname'], positions)
            reported_satellites.add(sat_id)

@tasks.loop(hours=24)
async def daily_report():
    now = datetime.now()
    if now.hour == 0:  # Run at midnight
        summary = "📊 **Daily Satellite Report** 📊\n"
        summary += f"Total satellites tracked: {len(reported_satellites)}\n"
        await send_to_discord(summary)
        logger.info("Sent daily report.")

# Discord Events
@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    monitor_satellites.start()
    daily_report.start()

client.run(TOKEN)
