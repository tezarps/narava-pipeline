#!/usr/bin/env python3
"""One-off generator for the comparative-mythology test episode 'The Great Flood'
(topic id=52, category=comparative). Same Haiku-draft -> Sonnet-polish pattern as
agents/script_agent.py, but the single-deity 'you serve god X' frame is replaced
with the archive-keeper frame device from content_plan_comparative_mythology/01_great_flood.txt.
Writes directly to output/scripts/52.txt so the normal pipeline (TTS/assembly/upload)
can pick it up as a cached script when topic 52 is scheduled."""
import pathlib
import anthropic
from config import ANTHROPIC_API_KEY, HAIKU_MODEL, SONNET_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_THROUGHLINE = """Sensory throughline (must appear in every segment): the sound of water — a
small trickle or rainfall building into the era's flood sound; the smell of wood and resin
from a boat or vessel; and the Keeper's hand touching a different texture for this shelf
(clay, leather, silk, marble, bamboo-and-ink — use the one named for this segment)."""

_ARCHIVE_OPEN = """You are writing the OPENING segment of a sleep story script for YouTube.

Niche: A Story Before You Sleep (comparative mythology format)
Episode: "The Great Flood" — five cultures remember the same night the water rose.

You ARE the Keeper of an archive that exists outside time, tending shelves that hold
"remembered nights" from across human history. Tonight, five shelves light up at once,
on their own, unbidden — all of them hold the memory of the same night: the night the
water rose and the old world ended.

Write the OPENING — target 900 words.

Structure:
- Establish the vast, quiet, candlelit archive. The Keeper's nightly rounds. Calm,
  curious tone — NOT ominous, NOT horror. The lights waking on their own is wonder, not warning.
- The Keeper notices the five shelves glowing and walks toward the first one, a cold
  clay tablet (Mesopotamia), already feeling its texture under their fingers as the
  segment ends — this is the bridge into the first memory.

Point of view: second person ("you"), present tense — the listener IS the Keeper, not
someone hearing about them. Never switch to "he/she/they" for the protagonist.

Tone: slow, descriptive, deeply sensory. No dialogue-heavy scenes. Flowing prose.
Output only the script text. No headers."""

_CULTURE_SEGMENT = """You are writing one segment of a sleep story script for YouTube — part
of the comparative-mythology episode "The Great Flood."

Frame: you ARE the Keeper of an archive of remembered nights. You have just touched a
{texture} on this shelf, and the memory pulls you in — for this segment, you become the
person living that night, in second person, present tense, fully immersed (not the Keeper
observing from outside — you ARE {protagonist}).

This segment's memory ({culture}): {beats}

{throughline}

Write this segment — target 950 words.

Structure:
- Brief bridge (1-2 sentences): the texture under your fingers dissolves into the memory itself.
- The memory, told fully immersive in second person, present tense, sensory and slow —
  the warning, the building/preparing, the rising water, the waiting, the first sign of safety.
- Brief bridge out (1-2 sentences): the memory fades, your hand is back on the shelf, the
  light dims, the archive's quiet returns.

Point of view: second person ("you"), present tense, throughout — even while inhabiting
{protagonist}. Never switch to "he/she/they" for them.

Tone: slow, descriptive, deeply sensory, calm even at the height of the flood — this is a
sleep story, not a disaster scene. No dialogue-heavy scenes. Flowing prose.
Output only the script text. No headers."""

_ARCHIVE_CLOSE = """You are writing the CLOSING segment of a sleep story script for YouTube —
the end of the comparative-mythology episode "The Great Flood."

Frame: you ARE the Keeper of the archive of remembered nights. All five shelves have now
been visited and are dimming, one by one, because they have been remembered tonight and can
rest. No moral, no "which one is true" conclusion — just the quiet realization that the
same water was remembered five different ways.

Write the CLOSING — target 900 words.

Structure:
- The fifth shelf (bamboo and ink, China) dims as you step back from it.
- A slow walk back through the archive's center aisle, the other four shelves already dark,
  candlelight settling.
- Pure ambient wind-down: the archive's silence, the smell of old parchment and dust
  settling, your own tiredness as the Keeper. You sit. The last candle is allowed to go out.
  The last 400 words should be almost entirely sensory — very little narrative action.

Point of view: second person ("you"), present tense, throughout. Never switch to "he/she/they".

Tone: increasingly slow and sleep-inducing, deeply peaceful.
Output only the script text. No headers."""

_POLISH = """You are a sleep content editor. Enhance this comparative-mythology sleep story
segment draft.

Rules:
1. {opening_rule}
2. Insert a sleep anchor every 4-5 paragraphs. Natural variations: "And as you listen...",
   "You feel yourself becoming heavier...", "Let your mind drift...", "The warmth surrounds
   you...", "There is nothing to do now but rest..."
3. Add "..." at natural breath points within sentences to slow the reading pace
4. Expand sensory details: if draft says "cold stone", describe that coldness for two full sentences
5. Keep all mythological/cultural content factually intact and respectful — this is
   comparative mythology, not a claim that any one tradition is correct
6. Do NOT add chapter headers or section markers

Draft:
{draft}

Output only the enhanced script."""

_OPENING_BUMPER = """Welcome... to A Story Before You Sleep... where the same old story is remembered differently, all around the world...

Tonight's story... The Great Flood — five cultures remember the same night the water rose...

Narrated by Rendy...

Close your eyes... breathe slowly... and let the old archive carry you..."""

SEGMENTS = [
    dict(
        culture="Mesopotamia (Epic of Gilgamesh)",
        protagonist="Utnapishtim",
        texture="cold clay tablet",
        beats=(
            "Utnapishtim is warned by the god Ea, speaking through the reed wall of his house, "
            "that the gods will flood the world. He builds a great boat at Shuruppak, seals it "
            "with pitch and bitumen, loads his family and the seed of every living thing. Rain "
            "falls for seven days. When it stops, he releases a raven, then a dove, to find dry land."
        ),
    ),
    dict(
        culture="Abrahamic tradition (Noah)",
        protagonist="Noah",
        texture="dry, cracked leather scroll",
        beats=(
            "Noah is told to build an ark of gopher wood, and to bring two of every animal, male "
            "and female. Rain falls for forty days and nights. The ark drifts until it rests on a "
            "mountain. A dove is sent out and returns with an olive branch. A rainbow appears as a sign."
        ),
    ),
    dict(
        culture="Hindu tradition (Manu and Matsya)",
        protagonist="Manu",
        texture="smooth silk cloth",
        beats=(
            "Manu finds a small fish in his washing water that asks for protection, growing larger "
            "every day until it is a vast being — Matsya, an avatar of Vishnu. The fish warns Manu of "
            "a coming flood and tells him to build a boat and gather the seeds of all plants and pairs "
            "of animals. When the flood comes, Manu ties the boat's rope to Matsya's horn, and the fish "
            "tows the boat to safety on a mountain peak."
        ),
    ),
    dict(
        culture="Greek tradition (Deucalion and Pyrrha)",
        protagonist="Deucalion",
        texture="cool marble tablet",
        beats=(
            "Zeus floods the earth to end an age of human wickedness. Deucalion and his wife Pyrrha, "
            "warned in advance, build a wooden chest and float on the waters until they land on Mount "
            "Parnassus. Afterward, guided by an oracle, they throw stones over their shoulders, and "
            "the stones become a new generation of people."
        ),
    ),
    dict(
        culture="Chinese tradition (the Great Flood and Yu the Engineer)",
        protagonist="Yu",
        texture="bamboo strip bound with ink-darkened thread",
        beats=(
            "Unlike the other memories, this is not one rescue in one night but generations of work. "
            "Gun tries to dam the floodwaters and fails. His son Yu succeeds by patiently carving "
            "channels to guide the water to the sea, traveling the land for years, wearing down his "
            "own body in service of the work, never resting in any one place until the water is tamed."
        ),
    ),
]


def _call(model, prompt, max_tokens=8000):
    r = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text


def generate_great_flood_script():
    finals = []

    print("Drafting OPENING (Haiku)...")
    draft_open = _call(HAIKU_MODEL, _ARCHIVE_OPEN)
    print("Polishing OPENING (Sonnet)...")
    opening_rule = f'Add this opening before paragraph 1, exactly as written:\n"""\n{_OPENING_BUMPER}\n"""'
    final_open = _call(SONNET_MODEL, _POLISH.format(draft=draft_open, opening_rule=opening_rule))
    finals.append(final_open.strip())

    for seg in SEGMENTS:
        print(f"Drafting segment: {seg['culture']} (Haiku)...")
        draft = _call(HAIKU_MODEL, _CULTURE_SEGMENT.format(
            culture=seg["culture"], protagonist=seg["protagonist"],
            texture=seg["texture"], beats=seg["beats"], throughline=_THROUGHLINE,
        ))
        print(f"Polishing segment: {seg['culture']} (Sonnet)...")
        opening_rule = "Do NOT add any welcome/opening line — this continues directly from the previous segment, already mid-story."
        final = _call(SONNET_MODEL, _POLISH.format(draft=draft, opening_rule=opening_rule))
        finals.append(final.strip())

    print("Drafting CLOSING (Haiku)...")
    draft_close = _call(HAIKU_MODEL, _ARCHIVE_CLOSE)
    print("Polishing CLOSING (Sonnet)...")
    opening_rule = "Do NOT add any welcome/opening line — this continues directly from the previous segment, already mid-story."
    final_close = _call(SONNET_MODEL, _POLISH.format(draft=draft_close, opening_rule=opening_rule))
    finals.append(final_close.strip())

    full_script = "\n\n".join(finals)
    word_count = len(full_script.split())
    print(f"\nScript: {word_count:,} words (~{word_count // 130:.0f} min audio)")
    return full_script


if __name__ == "__main__":
    script = generate_great_flood_script()
    out_path = pathlib.Path(__file__).parent / "output" / "scripts" / "52.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(script, encoding="utf-8")
    print(f"Tersimpan: {out_path}")
