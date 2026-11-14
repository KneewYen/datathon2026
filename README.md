# PortfolioGuard AI: A Multi-Agent Strategic Investor

**Team 62** · Nguyen Le · Vincent Deserres · Marc Fadous · Nic Zampieri

📖 **Full docs live in the [Wiki](https://github.com/KneewYen/datathon2026/wiki/Documentation-for-Datathon-2026-:-A-multi-agent-strategic-investor).**

- [Problem](https://github.com/KneewYen/datathon2026/wiki/Problem)
- [Solution](https://github.com/KneewYen/datathon2026/wiki/Solution)
- [Architecture](https://github.com/KneewYen/datathon2026/wiki/Architecture)
- [Agents](https://github.com/KneewYen/datathon2026/wiki/Agents)
- [Technologies](https://github.com/KneewYen/datathon2026/wiki/Technologies)
- [Impact](https://github.com/KneewYen/datathon2026/wiki/Impact)

## Structure
- `frontend/` Next.js app
- `backend/` FastAPI + agents (Bedrock)
- `lambda/` financial calculations (AWS Lambda)
- `data/` starter dataset (local only, synced to S3)
- `scripts/` helpers

## Setup
```bash
# backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn app.main:app --reload        # http://localhost:8000

# frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
```
