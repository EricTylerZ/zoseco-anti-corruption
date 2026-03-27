# Zoseco Anti-Corruption

Zoseco's first civic campaign. Launched on the Solemnity of Saint Joseph, 2025.

## What This Is

Zoseco began in 2014 as a gathering place for a few Air Force officers who enjoyed each other's company. Over the years it became something more. The anti-corruption effort was the first time the household entered a civic fight publicly, under its own name.

Valparaiso, Indiana was built by generations of honest people. That makes it a target for those who exploit honest systems. This project was built to consolidate what the community knows, recognize patterns that individuals cannot see alone, and make those patterns visible. Visibility is the one thing corruption cannot survive.

The effort was launched on Saint Joseph's feast day because the work was placed under specific patronage. Joseph is the guardian, the man entrusted with protecting something precious that was not his by origin but was his by duty. Guarding the integrity of a community is a duty, not an opinion.

## How It Works

The original implementation was a Flask chatbot deployed on Vercel, embedded in the Zoseco WordPress site. The WordPress frontend is no longer active. The backend architecture:

- **Backend**: Flask app on Vercel, powered by Venice AI API (`llama-3.1-405b`)
- **Storage**: Chat histories in Upstash Redis
- **Intake**: Conversations saved with metadata (timestamps, IP, token counts)
- **Admin**: Private endpoint for reviewing all submitted chats

## Current Status

The WordPress frontend was retired in March 2026 when zoseco.com migrated to the Community Shield platform. The `/anti-corruption` URL currently redirects to the About page on zoseco.com. The backend on Vercel may still be running.

This project is being evaluated for integration into the current ecosystem. The intelligence consolidation function connects to the work that Sentinel (Eric's OSINT platform) now handles, though this effort predates Sentinel by months. The tip submission and community intake function is something the Community Shield platform could host natively.

## Contact

- Phone: (219) 488-2689
- Email: info@zoseco.com
- Eric Zosso: eric@zoseco.com

## Repository

- **Created**: March 19, 2025
- **Organization**: [Zoseco Incorporated](https://zoseco.com)
- **Part of**: The [ericzosso.com](https://ericzosso.com) ecosystem
