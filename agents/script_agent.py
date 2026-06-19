import anthropic
from config import ANTHROPIC_API_KEY, HAIKU_MODEL, SONNET_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Four narrative frame devices, rotated by topic id, so the channel isn't a single
# fill-in-the-blank skeleton with only the deity name swapped (this directly targets
# YouTube's "inauthentic content" criterion of templated structure with little variation
# across uploads — see project memory project_narava_pipeline.md).
_FRAME_VARIANTS = {
    "servant": dict(
        part1_structure="""- OPENING: The ancient world at dawn. Set the scene. Where are we? The sounds, smells, light. Introduce the character's role and place in this mythological world.
- MORNING: The first rituals and duties of the day. Rich sensory detail — textures, warmth, sounds of this world. Interactions with minor characters. Atmosphere of the sacred space.
- MIDDAY: The height of activity. A key encounter or moment in this mythology. The warmth of the day. Deeper immersion into this world's rhythms.""",
        part2_structure="""- AFTERNOON: The day slowing. Quieter duties. The golden light of late afternoon. Peaceful routines.
- EVENING: The day ending. Fires lit, stars beginning to appear. Slower pace. The world becoming still.
- NIGHT WIND-DOWN: Pure ambient description. The ancient world sleeping. Stars. Silence. Distant sounds of water or wind. The character at rest. Fade gently into peaceful stillness.""",
        role_line="You are a servant/keeper/attendant living and working in the world of this mythology.",
        part2_open="Part 1 ended at midday.",
    ),
    "ritual": dict(
        part1_structure="""- PURIFICATION: Before dawn, you prepare your body and the sacred space for tonight's rite devoted to this myth — washing, dressing, lighting the first incense. Rich sensory detail.
- PROCESSION: You walk a slow ceremonial path toward the place where the rite will happen, joined at a distance by other quiet figures, the world around you waking.
- THE FIRST RITE: A key ceremonial act tied to this mythology's central story — an offering, a recitation, a symbolic re-enactment. Calm, reverent, unhurried.""",
        part2_structure="""- THE VIGIL: The ritual slows into a long quiet watch through the afternoon and evening, tending a flame or sacred object, the light changing around you.
- THE CLOSING RITE: The final ceremonial act as night falls, returning the sacred space to stillness.
- NIGHT WIND-DOWN: Pure ambient description. Incense smoke thinning. Candles guttering low. Silence settling over the ritual ground. Fade gently into peaceful stillness.""",
        role_line="You are an initiate taking part in a sacred rite devoted to this myth, moving through its ceremonial stages over one night.",
        part2_open="Part 1 ended at the first rite, just past midday.",
    ),
    "pilgrim": dict(
        part1_structure="""- SETTING OUT: Before dawn, you leave your home to begin a pilgrimage toward a shrine or sacred place tied to this mythology. The road, your pack, the quiet of early morning.
- THE ROAD: Midday travel — the landscape, small encounters with other travelers or locals, a resting point, sensory detail of heat, dust, water, shade.
- FIRST SIGHT: You catch your first glimpse of the sacred place itself, and a key story or detail of this mythology is revealed to you by something you see or someone you meet along the way.""",
        part2_structure="""- ARRIVAL AT DUSK: You reach the shrine as the light turns gold, and take in the place properly for the first time.
- THE OFFERING: A quiet, personal ritual act once you arrive — leaving something behind, a moment of stillness at the sacred site.
- NIGHT VIGIL: Pure ambient description. You settle to rest near the shrine for the night. Stars, distant sounds, the stillness of having arrived. Fade gently into peaceful stillness.""",
        role_line="You are a lone pilgrim journeying toward a place sacred to this mythology, over the course of one day and night.",
        part2_open="Part 1 ended with your first sight of the sacred place, around midday.",
    ),
    "caretaker": dict(
        part1_structure="""- LIGHTING THE LAMPS: Before dawn, you move through a sanctuary or temple devoted to this mythology, lighting lamps one by one, the building waking around you in shadow and gold.
- TENDING THE RELICS: Midmorning duties — cleaning, arranging, repairing small sacred objects and artifacts tied to this mythology's central stories, each one a quiet excuse to recall part of the myth.
- A STORY CARVED IN STONE: At midday, you pause at one particular relic or carving and a key moment of this mythology unfolds around you as if remembered through the object itself.""",
        part2_structure="""- QUIET AFTERNOON: Fewer visitors, slower duties, golden light through the sanctuary's windows or doorways.
- CLOSING THE SANCTUARY: As evening falls, you move through the space again in reverse, dimming each lamp, securing each relic for the night.
- NIGHT WIND-DOWN: Pure ambient description. The sanctuary in darkness but for one last lamp. Silence, stone, incense smoke. Fade gently into peaceful stillness.""",
        role_line="You are the caretaker of a sanctuary's relics and shrines devoted to this mythology, tending them through one full day and night.",
        part2_open="Part 1 ended with a story remembered through one of the relics, around midday.",
    ),
}

_VARIANT_ORDER = ["servant", "ritual", "pilgrim", "caretaker"]


def _frame_variant_for(topic_id):
    return _VARIANT_ORDER[int(topic_id) % len(_VARIANT_ORDER)]


_DRAFT_PART1 = """You are writing Part 1 of a sleep story script for YouTube.

Niche: Ancient Mythology for Sleep
Topic: {topic}
Angle: {angle}
Category: {category} mythology

{role_line}

Write Part 1 of 2 — target 2,750 words.

Structure:
{part1_structure}

Point of view: second person ("you"), present tense, throughout — the listener IS the
character, not someone hearing about them. This is the core of the brand: immersive
role-play, not third-person retelling. Never switch to "he/she/they" for the protagonist.
Keep "you" statements sensory and descriptive ("you feel the cool stone beneath your feet")
rather than presumptuous claims about the listener's own emotions ("you feel happy") —
describe the scene's effect on the body, not assert the listener's inner state.

Tone: slow, descriptive, present-tense, deeply sensory. No dialogue-heavy scenes. Flowing prose.
Output only the script text. No headers."""

_DRAFT_PART2 = """You are writing Part 2 of a sleep story script for YouTube.

Niche: Ancient Mythology for Sleep
Topic: {topic}
Angle: {angle}
Category: {category} mythology

{role_line}

{part2_open} Now write Part 2 of 2 — target 2,750 words.

Structure:
{part2_structure}

Point of view: second person ("you"), present tense, throughout — same as Part 1. The
listener IS the character. Never switch to "he/she/they" for the protagonist.

Tone: increasingly slow and sleep-inducing. The last 500 words should be almost entirely sensory — very little narrative action, just ambient beauty.
Output only the script text. No headers."""

_OPENING = """Welcome... to Ancient Mythology for Sleep... the channel that helps you drift into peaceful rest each night...

Tonight's story... {angle}...

Narrated by Shelby...

Close your eyes... breathe slowly... and let the ancient world carry you..."""

_POLISH = """You are a sleep content editor. Enhance this mythology sleep story draft.

Rules:
1. {opening_rule}
2. Insert a sleep anchor every 4-5 paragraphs. Natural variations: "And as you listen...", "You feel yourself becoming heavier...", "Let your mind drift...", "The warmth surrounds you...", "There is nothing to do now but rest..."
3. Add "..." at natural breath points within sentences to slow the reading pace
4. Expand sensory details: if draft says "warm air", describe that warmth for two full sentences
5. Keep all mythology content intact
6. Do NOT add chapter headers or section markers

Draft:
{draft}

Output only the enhanced script."""


def _call(model, prompt, max_tokens=8000):
    r = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text


def generate_script(topic_data):
    category = topic_data["category"]
    topic = topic_data["topic"]
    angle = topic_data["angle"]
    variant_key = _frame_variant_for(topic_data["id"])
    variant = _FRAME_VARIANTS[variant_key]

    opening = _OPENING.format(angle=angle)
    opening_rule_part1 = f'Add this opening before paragraph 1, exactly as written:\n"""\n{opening}\n"""'
    opening_rule_part2 = "Do NOT add any welcome/opening line — this continues directly from Part 1, already mid-story."

    print(f"    Frame variant: {variant_key}")
    print("    Drafting Part 1 (Haiku)...")
    draft1 = _call(HAIKU_MODEL, _DRAFT_PART1.format(
        topic=topic, angle=angle, category=category,
        role_line=variant["role_line"], part1_structure=variant["part1_structure"],
    ))

    print("    Drafting Part 2 (Haiku)...")
    draft2 = _call(HAIKU_MODEL, _DRAFT_PART2.format(
        topic=topic, angle=angle, category=category,
        role_line=variant["role_line"], part2_structure=variant["part2_structure"],
        part2_open=variant["part2_open"],
    ))

    print("    Polishing Part 1 (Sonnet)...")
    final1 = _call(SONNET_MODEL, _POLISH.format(draft=draft1, opening_rule=opening_rule_part1))

    print("    Polishing Part 2 (Sonnet)...")
    final2 = _call(SONNET_MODEL, _POLISH.format(draft=draft2, opening_rule=opening_rule_part2))

    full_script = final1.strip() + "\n\n" + final2.strip()
    word_count = len(full_script.split())
    print(f"    Script: {word_count:,} words (~{word_count // 130:.0f} min audio)")
    return full_script
