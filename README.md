# Anti-Corruption Bot

A simple AI-powered chatbot to help understand corruption scenarios in Valparaiso, Indiana.

## Overview

The Anti-Corruption Bot is live at [zoseco.com/anti-corruption](https://zoseco.com/anti-corruption). It’s designed to:
- Gather details about corruption rumors and situations in Valparaiso, Indiana.
- Ask clarifying questions about key players and allegations.
- Provide insights without suggesting reporting to authorities.

## How It Works

- **Frontend**: A chat interface built into the Zoseco WordPress site using Divi.
- **Backend**: A Flask app hosted on Vercel, powered by the Venice AI API (`llama-3.1-405b` model).
- **Storage**: Chat histories are stored in Upstash Redis with a 24-hour expiration.

## Usage

1. Visit [zoseco.com/anti-corruption](https://zoseco.com/anti-corruption).
2. Type a question or statement about corruption in Valparaiso, Indiana (e.g., "Rumors about a shady official").
3. The bot responds with questions or insights to explore the scenario further.

## Features

- Conversations are saved with metadata (timestamps, IP, token counts).
- Admin access to view all chats (via a private endpoint).

## Setup

- **Deployed on Vercel**: Backend runs at `https://anti-corruption-bot.vercel.app`.
- **Environment Variables**: Configured in Vercel (e.g., `VENICE_API_KEY`, `SYSTEM_PROMPT`).
- **Local Testing**: Not included here—contact the admin for details.

## Future Plans

- Add web3 wallet authentication for secure access.
- Extend chat retention beyond 24 hours if needed.

## Contact

For questions or support, reach out to the Zoseco team.