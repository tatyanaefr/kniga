# Озвучивает слоги и фразы приложения нейроголосом Microsoft и кладёт mp3 в папку audio.
# Тишину в начале и в конце обрезает — чтобы слоги шли друг за другом ровно.
# Уже озвученное не трогает. Переозвучить всё: запустить с ключом --заново.

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import edge_tts

VOICE = "ru-RU-SvetlanaNeural"
RATE_SYL = "-15%"     # слова и слоги — чуть медленнее обычной речи
RATE_PHRASE = "+0%"
PITCH = "+15Hz"       # выше и мягче, как в трекере

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "audio"

TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,"
        "areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,"
        "areverse,"
        "apad=pad_dur=0.04")


def fnv(text):
    """Имя файла по тексту — так же считает приложение (FNV-1a)."""
    h = 0x811C9DC5
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return format(h, "08x")


def trim(raw, target):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", TRIM,
                    "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", str(target)], check=True)
    raw.unlink()


async def speak(text, sem, again):
    target = AUDIO / f"{fnv(text)}.mp3"
    if target.exists() and not again:
        return False
    raw = AUDIO / f"{fnv(text)}.raw.mp3"
    is_syl = len(text.split()) <= 2 and not any(c in text for c in "!?,.")
    say = text + "." if is_syl else text
    async with sem:
        for attempt in range(3):
            try:
                await edge_tts.Communicate(say, VOICE, rate=RATE_SYL if is_syl else RATE_PHRASE, pitch=PITCH).save(str(raw))
                await asyncio.to_thread(trim, raw, target)
                return True
            except Exception as e:
                if attempt == 2:
                    print("Не получилось:", text, "—", e)
                await asyncio.sleep(2)
    return False


async def main():
    again = "--заново" in sys.argv
    AUDIO.mkdir(exist_ok=True)
    out = subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require(process.argv[1]).allAudioTexts()))",
                          str(ROOT / "data.js")], capture_output=True, check=True)
    texts = json.loads(out.stdout.decode("utf-8"))
    sem = asyncio.Semaphore(4)
    made = await asyncio.gather(*(speak(t, sem, again) for t in texts))
    ready = [fnv(t) for t in texts if (AUDIO / f"{fnv(t)}.mp3").exists()]
    (AUDIO / "index.json").write_text(json.dumps(ready), encoding="utf-8")
    print(f"Всего кусочков: {len(texts)}, озвучено сейчас: {sum(made)}, готово: {len(ready)}")


asyncio.run(main())
