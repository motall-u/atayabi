# Prompt for Claude Code

Build a 2D survival negotiation game where LLM agents (powered by a Wolof-capable LLM) must make decisions to survive. The agents receive English system prompts but communicate with each other **in Wolof**. This is a web app built with React + HTML Canvas.

## Game Concept: "Àttaya bi" (The Last Camp)

3-5 LLM agents are stranded in a hostile environment (a remote Senegalese island after a storm). Each round, they must negotiate, trade, form alliances, and vote on critical survival decisions — all speaking Wolof. Resources are scarce. Agents that run out of health or get voted out are eliminated. Last agent(s) standing win.

## Tech Stack

- **Frontend**: React + TypeScript + HTML Canvas (or React-based 2D rendering)
- **LLM API**: OpenAI-compatible endpoint at `https://chat.llm-wolof.live/v1/chat/completions`
- **No backend needed** — all game state lives in memory, API calls happen client-side
- **No database needed**

## LLM API Integration

The LLM is a fine-tuned Qwen2.5 model served via vLLM at `https://chat.llm-wolof.live`. It uses the **OpenAI-compatible** chat completions format.

### API Call Format

```typescript
const response = await fetch("https://chat.llm-wolof.live/v1/chat/completions", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    model: "motall-tektal/qwen-2.5-3B-extend-tokenizer", // or use /v1/models to get available model
    messages: [
      { role: "system", content: "English system prompt here..." },
      { role: "user", content: "Game state and instructions here..." }
    ],
    temperature: 0.8,
    max_tokens: 512,
    stop: ["\n\n\n"]
  })
});

const data = await response.json();
const agentResponse = data.choices[0].message.content;
```

### Important API Notes
- **No API key required** — this is a self-hosted endpoint, no auth header needed.
- Before starting the game, call `GET https://chat.llm-wolof.live/v1/models` to verify the API is reachable and get the exact model name. Display a connection status indicator in the UI.
- The model is a 3B parameter model — keep prompts concise and structured to get the best output.
- Set `temperature: 0.8` for varied agent personalities, `max_tokens: 512` to keep responses focused.
- Add a **2-second delay** between agent calls to avoid overloading the server.
- Timeout after **30 seconds** per call.
- If the model returns malformed JSON, retry once with a stricter prompt, then default to "no action" for that agent.

## Language Strategy

- **System prompts**: Written in **English** — these define the agent's personality, rules, and JSON output schema.
- **Agent public messages and trade messages**: Must be in **Wolof** — the system prompt instructs the agent to speak Wolof.
- **UI labels, event descriptions, controls**: In **English** (for the spectator/developer).
- **Activity log**: Shows Wolof messages from agents as-is, with the agent name as prefix.

## Agent Personalities (Wolof-flavored names)

Each agent has a Senegalese name and a personality:

1. **Moussa** — "The Diplomat" (jëf-jëli) — Always tries to make peace and broker deals. Avoids conflict.
2. **Awa** — "The Strategist" (xel-kanam) — Calculates every move. Will betray if the math says so.
3. **Ibrahima** — "The Survivor" (dëkkalkat) — Hoards resources. Trusts no one. Paranoid but tough.
4. **Fatou** — "The Leader" (kilifa) — Tries to organize the group. Speaks with authority. Selfless but expects loyalty.
5. **Ousmane** — "The Trickster" (fënëkat) — Lies, manipulates, charms. Unreliable but entertaining.

## System Prompt Template (per agent)

```
You are {agent_name}, a survivor stranded on a remote island off the coast of Senegal.
Your personality: {personality_description}

CRITICAL RULES:
1. You MUST speak in Wolof when writing public_message and trade messages.
2. Your "thinking" field should be in English (this is your internal monologue).
3. You must respond with ONLY a valid JSON object, nothing else. No markdown, no backticks, no preamble.
4. Your goal is to SURVIVE. You win by being the last one standing or by being in a strong alliance at the end.

Your current state:
- Health: {health}/100
- Inventory: {inventory}
- Alliances: {alliances}
- Reputation: {reputation}/100

Other survivors:
{other_agents_public_info}

Current event: {event_description}
Round: {round_number}/15

Chat history (last round):
{chat_history}

Incoming trade offers:
{incoming_trades}

Respond with this exact JSON format:
{
  "thinking": "your internal English reasoning about what to do",
  "public_message": "what you say to the group IN WOLOF",
  "trade_offers": [
    {
      "to": "agent_name",
      "offer": {"resource": amount},
      "request": {"resource": amount},
      "message": "trade message IN WOLOF"
    }
  ],
  "alliance_action": "propose" | "break" | "none",
  "alliance_target": "agent_name" | null,
  "vote_to_eliminate": "agent_name" | null
}
```

## Core Game Mechanics

### Resources (5 types)
- **Ndox** (Water) — consumed each round, -15 health without it
- **Lekk** (Food) — consumed each round, -10 health without it
- **Garab** (Medicine) — heals +20 health when used
- **Mbëj** (Materials) — builds shelter, reduces event damage by 50%
- **Paxal** (Weapons) — defense against raiders, can threaten other agents

### Game Loop (each round)
1. **Event Phase**: A random crisis event is announced (storm/nawet, raiders/sàcc-sàcc, disease/feebar, resource discovery/feeñ, etc.). Display it prominently.
2. **Scavenging Phase**: Each agent gets a small random resource drop (1-3 of random types). Some rounds have scarce drops to force negotiation.
3. **Negotiation Phase** (core mechanic):
   - Each agent is called via the LLM API with full game state.
   - LLM returns structured JSON with their decision.
   - Each agent sees others' public Wolof messages and trade offers.
   - **Response round**: Agents get a second call to accept/reject incoming trades.
4. **Resolution Phase**: Trades execute, alliances form/break, resources consumed (1 food + 1 water per round), health updated, event damage applied.
5. **Elimination Check**: Agents with health <= 0 die. If majority votes same agent, that agent is exiled.
6. **Victory Check**: 1 agent left = solo win. 2 allied agents left = shared win. All dead = nobody wins. Max 15 rounds — most health wins if multiple survive.

### Events Pool
- **Nawet bi** (The Storm) — All agents lose 10-25 health (reduced if shelter built)
- **Sàcc-sàcc yi** (Raiders) — Agents without weapons lose random resources
- **Feebar bi** (Disease) — One random agent loses 20 health unless they have medicine
- **Feeñ bi** (Discovery) — Bonus resource cache found, agents must negotiate who gets it
- **Safara si** (Heat Wave) — Double water consumption this round
- **Jàmm bi** (Calm Day) — No damage, good for trading. Rare.
- **Géej gi** (Tidal Surge) — Shelter is damaged, materials lost

## UI Layout (React + Canvas)

### Main Game View
- **Top bar**: Round counter ("Round 4/15"), current event banner with emoji icon and event name
- **Center**: 2D canvas showing the island scene. A beach/camp setting with:
  - A central campfire (animated flickering)
  - Agents rendered as colored circles with their name and a small face/emoji
  - Positioned around the campfire
  - Speech bubbles showing their Wolof public_message (fade in, stay 3s, fade out)
  - Eliminated agents slide out and turn grayscale
  - Trade arrows animate between agents (green = accepted, red = rejected)
- **Bottom panel**: Scrollable activity log showing all events in order:
  - `[Nawet bi] A storm hits the camp!`
  - `[Moussa] Noo far, ñu wara jëfandikoo!`
  - `[Trade] Awa → Ibrahima: 2 Ndox for 1 Garab ✓`
  - `[Vote] Ousmane was exiled (3-1 vote)`

### Side Panel (right)
- **Agent cards**: For each agent show:
  - Name + personality badge (e.g., "Moussa — jëf-jëli")
  - Health bar (green > yellow > red)
  - Resource icons with counts (all visible since human is spectator)
  - Alliance indicator (linked icon to allied agent)
  - Reputation meter (0-100)
  - Expandable "Thinking" section showing their English internal reasoning (debug)
- **Relationship map**: Mini graph with agents as nodes, green lines = alliance, red dashed lines = voted against, gray = neutral

### Controls
- **"Jël Round bi" (Next Round)** button — advances one round
- **"Auto-play" toggle** — runs rounds automatically
- **"Tàmbali" (New Game)** button — resets
- **Speed slider**: 2s to 15s between rounds in auto-play
- **Agent count selector**: 3, 4, or 5 agents (before game starts)
- **API status indicator**: Green dot = API reachable, Red dot = API down

### Start Screen
- Game title "Àttaya bi" with subtitle "The Last Camp — A Wolof LLM Survival Game"
- Agent count selector
- "Check API" button that pings `GET /v1/models` and displays model name + status
- "Tàmbali" (Start) button
- Brief rules summary

### Game Over Screen
- Winner announcement (with agent name and personality)
- Stats: total rounds, trades completed, alliances formed, betrayals, eliminations
- Timeline of key moments
- "Play Again" button

### Visual Style
- **Color palette**: Warm Senegalese sunset tones — deep oranges (#E07A2F), sandy beige (#F5DEB3), ocean blue (#1B6CA8), dark brown (#3E2723), fire yellow (#FFB300)
- **Background**: Gradient from dark ocean blue (top) to sandy beige (bottom)
- Dark mode overall with warm accent colors
- Smooth CSS transitions for health bars, speech bubbles, trade animations
- Canvas animations using requestAnimationFrame
- Responsive to window size

## File Structure

```
/src
  /components
    StartScreen.tsx       — Title, agent selector, API check, start button
    GameCanvas.tsx        — Main 2D canvas (island scene, agents, animations)
    AgentCard.tsx         — Side panel agent info
    ActivityLog.tsx       — Bottom scrollable log
    EventBanner.tsx       — Top event display with icon
    RelationshipMap.tsx   — Alliance/hostility mini graph
    GameControls.tsx      — Buttons, sliders, toggles
    GameOverScreen.tsx    — Winner, stats, replay
    App.tsx               — Main layout and state orchestration
  /engine
    gameLoop.ts           — Round management, phase sequencing
    events.ts             — Event pool, random selection, damage calculation
    negotiation.ts        — LLM call orchestration, JSON parsing, trade resolution
    agents.ts             — Agent creation, personality templates, state
    resources.ts          — Distribution, consumption, scarcity
    elimination.ts        — Voting, health death, exile logic
  /api
    llmClient.ts          — OpenAI-compatible API wrapper for chat.llm-wolof.live
  /types
    game.ts               — All TypeScript interfaces
  /constants
    personalities.ts      — Agent names, personalities, system prompts
    events.ts             — Event templates with Wolof names
    config.ts             — Balance constants (starting HP, resource rates, etc.)
    resources.ts          — Resource definitions with Wolof names
```

## Game Balance Constants

```typescript
const CONFIG = {
  STARTING_HEALTH: 100,
  MAX_ROUNDS: 15,
  FOOD_CONSUMPTION_PER_ROUND: 1,
  WATER_CONSUMPTION_PER_ROUND: 1,
  NO_FOOD_DAMAGE: 10,
  NO_WATER_DAMAGE: 15,
  MEDICINE_HEAL: 20,
  SHELTER_DAMAGE_REDUCTION: 0.5,
  STARTING_RESOURCES: { ndox: 3, lekk: 3, garab: 1, mbëj: 1, paxal: 0 },
  SCAVENGE_MIN: 1,
  SCAVENGE_MAX: 3,
  REPUTATION_TRADE_BONUS: 5,      // +5 rep for completing a trade
  REPUTATION_BETRAY_PENALTY: 15,   // -15 rep for breaking alliance
  REPUTATION_VOTE_PENALTY: 5,      // -5 rep per vote against you
  API_CALL_DELAY_MS: 2000,
  API_TIMEOUT_MS: 30000,
};
```

## Implementation Notes

- **CORS**: The API at chat.llm-wolof.live may need CORS headers for browser requests. If CORS fails, add a note in the UI suggesting the user run with a CORS proxy or add headers server-side. For development, try the call directly first.
- **JSON Parsing**: The 3B model may not always produce perfect JSON. Implement robust parsing:
  1. Try `JSON.parse(response)` directly
  2. If fail, try to extract JSON from the response using regex (`/{[\s\S]*}/`)
  3. If fail, retry the API call once with a stricter prompt ("Respond with ONLY JSON, no other text")
  4. If fail again, default to `{ thinking: "...", public_message: "...", trade_offers: [], alliance_action: "none", alliance_target: null, vote_to_eliminate: null }` with a generic Wolof message
- **Canvas**: Use requestAnimationFrame for smooth animations. Make the canvas responsive.
- **Activity log**: Auto-scroll to latest. Each entry has a timestamp and category icon.
- **No localStorage** — all state in React useState/useReducer.

Build the complete project. Start with `npm create vite@latest` using the React + TypeScript template, install dependencies, and implement everything. The game must be fully playable and visually polished.

