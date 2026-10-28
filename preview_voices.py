# preview_voices.py
"""
SPIDY Voice Selector & Preview Tool

Allows you to listen to samples of all top voices directly through your speakers,
and select your favorite one as your default assistant voice.
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import edge_tts
import miniaudio
import sounddevice as sd
from audio_cues import play_cue


VOICE_CANDIDATES = [
    {
        "id": "1",
        "name": "Brian",
        "voice": "en-US-BrianNeural",
        "gender": "Male",
        "style": "Modern, natural, approachable (Recommended)",
        "sample": "Hello! I am Brian. I can manage your windows, read your screen, and keep your workday organized.",
    },
    {
        "id": "2",
        "name": "Ava",
        "voice": "en-US-AvaNeural",
        "gender": "Female",
        "style": "Expressive, pleasant, conversational (Like modern Siri/ChatGPT)",
        "sample": "Hi there! I am Ava. I am here to help you get your daily tasks done quickly and smoothly.",
    },
    {
        "id": "3",
        "name": "Andrew",
        "voice": "en-US-AndrewNeural",
        "gender": "Male",
        "style": "Confident, authentic, clear and direct",
        "sample": "Good day. I am Andrew. Systems are ready, and I am standing by to assist with your work.",
    },
    {
        "id": "4",
        "name": "Emma",
        "voice": "en-US-EmmaNeural",
        "gender": "Female",
        "style": "Cheerful, crisp, and conversational",
        "sample": "Hello! I am Emma. Ready to help you review documents, search the web, and run your tasks.",
    },
    {
        "id": "5",
        "name": "Jarvis (Ryan)",
        "voice": "en-GB-RyanNeural",
        "gender": "Male",
        "style": "British, calm, sophisticated butler tone",
        "sample": "At your service, Sir. All diagnostic systems are nominal. What shall we tackle first?",
    },
    {
        "id": "6",
        "name": "Friday (Emily)",
        "voice": "en-IE-EmilyNeural",
        "gender": "Female",
        "style": "Tactical Irish accent, crisp and efficient",
        "sample": "Hey Boss! Friday online. I've got your screen and tasks lined up whenever you're ready.",
    },
    {
        "id": "7",
        "name": "Neerja",
        "voice": "en-IN-NeerjaExpressiveNeural",
        "gender": "Female",
        "style": "Indian English, expressive and natural",
        "sample": "Namaste! I am Neerja. I can help you organize your daily work and monitor your tasks.",
    },
    {
        "id": "8",
        "name": "Prabhat",
        "voice": "en-IN-PrabhatNeural",
        "gender": "Male",
        "style": "Indian English, polite and clear",
        "sample": "Hello! I am Prabhat. Standing by to assist you with your files, coding, and workflow.",
    },
    {
        "id": "9",
        "name": "Thomas",
        "voice": "en-GB-ThomasNeural",
        "gender": "Male",
        "style": "Classic British gentleman, formal and steady",
        "sample": "Good day. I am Thomas. Ready to assist with your computer operations whenever you require.",
    },
]


import numpy as np

async def _synthesize_and_play(voice_name: str, text: str) -> None:
    """Stream speech in memory and play through speakers."""
    communicate = edge_tts.Communicate(text=text, voice=voice_name, rate="+16%")
    mp3_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_bytes += chunk["data"]

    decoded = miniaudio.decode(mp3_bytes)
    audio_array = np.array(decoded.samples, dtype=np.int16).reshape(-1, decoded.nchannels)
    sd.play(audio_array, decoded.sample_rate)
    sd.wait()


def play_voice_sample(item: dict) -> None:
    """Play a sample of the chosen voice."""
    print(f"\n[Playing]: {item['name']} ({item['gender']} - {item['voice']})")
    print(f"Sample text: \"{item['sample']}\"")
    play_cue("confirm")
    asyncio.run(_synthesize_and_play(item["voice"], item["sample"]))
    play_cue("done")


def save_voice_selection(item: dict) -> None:
    """Save selected voice into .env file."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("SPIDY_VOICE="):
            new_lines.append(f"SPIDY_VOICE={item['voice']}\n")
            updated = True
        elif line.strip().startswith("SPIDY_PERSONALITY="):
            p = "friday" if "emily" in item["voice"].lower() else "jarvis" if "ryan" in item["voice"].lower() else "custom"
            new_lines.append(f"SPIDY_PERSONALITY={p}\n")
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"\nSPIDY_VOICE={item['voice']}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"\n[SUCCESS]: Voice saved! Default voice is now: {item['name']} ({item['voice']})")


def interactive_menu() -> None:
    """Display interactive numbered menu."""
    print("=" * 65)
    print("           SPIDY VOICE AUDITION & SELECTOR")
    print("=" * 65)
    print("Listen to each voice through your speakers and choose your favorite:\n")

    for v in VOICE_CANDIDATES:
        print(f"  [{v['id']}] {v['name']:<16} ({v['gender']}, {v['style']})")

    print("\nControls:")
    print("  * Enter a number [1-9] to hear that voice.")
    print("  * Type 'set <number>' (e.g. 'set 1') to select it as your permanent voice.")
    print("  * Type 'play all' to hear a preview of each voice sequentially.")
    print("  * Type 'exit' to quit.\n")

    while True:
        try:
            choice = input("Enter choice > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not choice or choice in ("exit", "quit", "q"):
            print("Exiting.")
            break

        if choice == "play all":
            for v in VOICE_CANDIDATES:
                play_voice_sample(v)
            continue

        if choice.startswith("set "):
            num = choice.replace("set", "").strip()
            matched = [v for v in VOICE_CANDIDATES if v["id"] == num or v["name"].lower() == num]
            if matched:
                save_voice_selection(matched[0])
                break
            else:
                print(f"Unknown voice number: {num}")
            continue

        # Single number check
        matched = [v for v in VOICE_CANDIDATES if v["id"] == choice or v["name"].lower() == choice]
        if matched:
            play_voice_sample(matched[0])
            print(f"-> Like this voice? Type 'set {matched[0]['id']}' to save it, or pick another number to hear more.")
        else:
            print("Please enter a number between 1 and 9, 'set <number>', or 'play all'.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--play-sample":
        voice_id = sys.argv[2] if len(sys.argv) > 2 else "1"
        matched = [v for v in VOICE_CANDIDATES if v["id"] == voice_id or v["name"].lower() == voice_id.lower()]
        if matched:
            play_voice_sample(matched[0])
        else:
            print(f"Voice {voice_id} not found.")
    else:
        interactive_menu()
