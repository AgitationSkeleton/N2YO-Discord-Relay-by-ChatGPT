# Satellite Discord Bot

![Satellite Bot Image](https://files.catbox.moe/ag0wo8.png)

This is a Discord bot written by ChatGPT which queries N2YO for satellites overhead a given area. To use it, you will need an API key (free with signup up to 1000 uses per hour) for N2YO and a key for OpenCage (also free, up to 2500 uses a day) if you want approximated locations for coordinates. This was created by ChatGPT and I claim none of it other than a few hours' worth of back and forth debugging with it.

## Required Packages

You will need the following Python packages:

```bash
pip install discord.py==2.0.0
pip install requests==2.28.1
pip install python-dotenv==0.21.1
