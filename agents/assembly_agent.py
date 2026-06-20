import math
import shutil
import subprocess
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import IMAGES_DIR, OUTPUT_DIR

FPS = 25
SLIDE_DURATION = 10  # seconds per image (Ken Burns)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
MUSIC_DIR = ASSETS_DIR / "music"
AMBIENCE_DIR = ASSETS_DIR / "ambience"
THUMBNAILS_DIR = Path(__file__).parent.parent / "thumbnails"

# Thumbnail brand assets — bundled in-repo (not OS fonts) so rendering is
# identical on a Mac and on a GitHub Actions Ubuntu runner. See project memory
# feedback_narava_thumbnail_workflow.md: brand line is fixed text, episode
# title is the dynamic subtitle underneath it.
CINZEL_BOLD = str(ASSETS_DIR / "fonts" / "Cinzel-Bold.ttf")
LATO_REGULAR = str(ASSETS_DIR / "fonts" / "Lato-Regular.ttf")
LOGO_PATH = ASSETS_DIR / "logo_narava.png"
HEADLINE = "ANCIENT MYTHOLOGY FOR SLEEP"
GOLD_TOP = (228, 158, 34)      # #e49e22
GOLD_BOTTOM = (242, 226, 157)  # #f2e29d

# Per-topic-id contextual ambience timeline: ordered list of (ambience_track_name,
# weight). Weights are each segment's *target* word count from the generator script
# that produced topic's narration (e.g. generate_great_flood_script.py) — used as a
# proportional approximation of that segment's share of total audio duration. Not
# frame-accurate, but ambience is a soft background layer, not lyric-synced, so this
# is precise enough. When a topic_id has an entry here, it REPLACES the static
# per-category assets/music/ track for that video; topics with no entry keep the
# old static-music behavior unchanged.
AMBIENCE_MAPS = {
    52: [  # The Great Flood (comparative) — see content_plan_comparative_mythology/01_great_flood.txt
        ("temple_hall", 900),    # archive open
        ("rain", 950),           # Mesopotamia — Utnapishtim, seven days of rain
        ("ocean_waves", 950),    # Abrahamic — Noah's ark adrift on the flood
        ("river_stream", 950),   # Hindu — Manu towed across the water by Matsya
        ("rain", 950),           # Greek — Zeus's flood, Deucalion and Pyrrha's chest
        ("river_stream", 950),   # Chinese — Yu channeling the floodwaters for generations
        ("temple_hall", 900),    # archive close
    ],
}


def _build_ambience_track(segments, total_duration_sec, out_path):
    """Build one continuous ambience track spanning total_duration_sec, switching
    source clip per segment proportional to its weight. Simple hard-cut concat
    (no crossfade) — matches this codebase's preference for simple, reliable ffmpeg
    chains over fancier filters; ambience is mixed quiet under narration so a cut
    between textures (e.g. rain -> river) isn't jarring."""
    total_weight = sum(w for _, w in segments)
    seg_dir = out_path.parent / f"_ambience_segs_{out_path.stem}"
    seg_dir.mkdir(exist_ok=True)
    seg_paths = []
    try:
        for i, (name, weight) in enumerate(segments):
            src = AMBIENCE_DIR / f"{name}.mp3"
            if not src.exists():
                raise FileNotFoundError(f"Missing ambience track: {src}")
            dur = total_duration_sec * weight / total_weight
            seg_path = seg_dir / f"{i:02d}_{name}.mp3"
            subprocess.run([
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
                "-t", f"{dur:.3f}",
                "-c:a", "libmp3lame", "-b:a", "192k", str(seg_path)
            ], capture_output=True, check=True)
            seg_paths.append(seg_path)

        concat_file = seg_dir / "concat.txt"
        concat_file.write_text("\n".join(f"file '{p.resolve()}'" for p in seg_paths))
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:a", "libmp3lame", "-b:a", "192k", str(out_path)
        ], capture_output=True, check=True)
    finally:
        shutil.rmtree(seg_dir, ignore_errors=True)


def get_manual_thumbnails(category, topic_slug):
    """Return (A_path, B_path) from thumbnails folder. Either can be None."""
    base = THUMBNAILS_DIR / category.lower() / topic_slug.lower()
    a, b = None, None
    for ext in (".jpg", ".jpeg", ".png"):
        if not a and (base / f"A{ext}").exists():
            a = base / f"A{ext}"
        if not b and (base / f"B{ext}").exists():
            b = base / f"B{ext}"
    return a, b


def _get_music(category):
    """Find music file for category — supports .wav and .mp3."""
    for ext in (".wav", ".mp3"):
        path = MUSIC_DIR / f"{category.lower()}{ext}"
        if path.exists():
            return path
    return None


def _get_images(category, topic_slug=None, count=10):
    candidates = []
    if topic_slug:
        topic_dir = IMAGES_DIR / category.lower() / topic_slug.lower()
        if topic_dir.exists():
            candidates = sorted(topic_dir.glob("*.jpg")) + sorted(topic_dir.glob("*.png")) + sorted(topic_dir.glob("*.jpeg"))
    if not candidates:
        cat_dir = IMAGES_DIR / category.lower()
        if cat_dir.exists():
            candidates = sorted(cat_dir.glob("*.jpg")) + sorted(cat_dir.glob("*.png")) + sorted(cat_dir.glob("*.jpeg"))
    if not candidates:
        candidates = sorted(IMAGES_DIR.glob("*.jpg")) + sorted(IMAGES_DIR.glob("*.png"))
    if not candidates:
        raise FileNotFoundError(f"No images found in images/{category.lower()}/{topic_slug or ''}/")
    return [candidates[i % len(candidates)] for i in range(count)]


def _make_ken_burns_clip(img_path, out_path):
    """Generate a slide clip with a subtle, smooth zoom-in (Ken Burns).

    zoompan rounds the crop window to whole pixels every frame; with too
    little headroom between the pre-scaled source and the 1920x1080 output,
    that window barely moves frame-to-frame and the rounding shows up as
    visible stair-step shake. Pre-scaling the source far beyond what the
    zoom range needs (8x here) gives the rounding enough room to land on a
    different pixel every frame, which is what actually reads as smooth.
    """
    d = SLIDE_DURATION * FPS  # total frames e.g. 250
    t = f"min(on,{d-1})/{d-1}"  # normalized 0→1
    ease = f"(3*pow({t},2)-2*pow({t},3))"  # smooth-step ease in-out

    # Crop window goes from 1990px-equivalent (slightly wider) at t=0 down
    # to 1920px (full, uncropped frame) at t=10 — a gentle, single-direction
    # zoom in, expressed as a zoompan z ratio.
    z_max = 1990 / 1920
    z = f"1+{z_max - 1:.7f}*{ease}"

    pre_w, pre_h = 7680, 4320  # 4x final res — anti-jitter headroom for zoompan

    vf_parts = [
        f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase",
        f"crop={pre_w}:{pre_h}",
        f"zoompan=z='{z}':d={d}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={FPS}",
        "setsar=1",
    ]
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_path),
        "-vf", ",".join(vf_parts),
        "-t", str(SLIDE_DURATION),
        "-r", str(FPS),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Ken Burns failed for {img_path.name}: {result.stderr[-300:]}")


def _audio_duration(audio_path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def _v_gradient(size, top_rgb, bottom_rgb):
    w, h = size
    col = Image.new("RGB", (1, max(h, 1)))
    for y in range(h):
        t = y / max(h - 1, 1)
        col.putpixel((0, y), tuple(int(top_rgb[i] + (bottom_rgb[i] - top_rgb[i]) * t) for i in range(3)))
    return col.resize((w, h))


def _text_width(d, text, font, tracking=0):
    if not tracking:
        return d.textbbox((0, 0), text, font=font)[2]
    return sum(d.textbbox((0, 0), ch, font=font)[2] for ch in text) + tracking * (len(text) - 1)


def _draw_text_layer(text, font, glow_color=None, fill_gradient=None, solid_color=None, tracking=0,
                      glow_blur=14, glow_alpha=0.85, glow_offset=(0, 0)):
    """Renders `text` onto its own tight RGBA layer (with padding for blur bleed),
    filled either with a vertical gradient or a solid color, with an optional
    soft glow behind it, and optional letter-spacing. Returns (layer, (text_w, text_h))."""
    tmp = Image.new("L", (1, 1))
    d = ImageDraw.Draw(tmp)
    pad = 36
    if tracking:
        char_widths = [d.textbbox((0, 0), ch, font=font)[2] for ch in text]
        tw = sum(char_widths) + tracking * (len(text) - 1)
        bbox = d.textbbox((0, 0), text, font=font)
        th = bbox[3] - bbox[1]
        mask = Image.new("L", (tw + pad * 2, th + pad * 2), 0)
        dm = ImageDraw.Draw(mask)
        x = pad
        for ch, cw in zip(text, char_widths):
            dm.text((x, pad - bbox[1]), ch, font=font, fill=255)
            x += cw + tracking
    else:
        bbox = d.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        mask = Image.new("L", (tw + pad * 2, th + pad * 2), 0)
        ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=255)

    layer = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    if glow_color:
        glow_mask = mask.filter(ImageFilter.GaussianBlur(glow_blur))
        glow = Image.new("RGBA", mask.size, glow_color + (0,))
        glow.putalpha(glow_mask.point(lambda a: int(a * glow_alpha)))
        layer.alpha_composite(glow, glow_offset)

    if fill_gradient:
        fill = _v_gradient(mask.size, *fill_gradient).convert("RGBA")
    else:
        fill = Image.new("RGBA", mask.size, solid_color)
    fill.putalpha(mask)
    layer.alpha_composite(fill)
    return layer, (tw, th), pad


def create_thumbnail(image_path, title, out_path):
    try:
        return _render_thumbnail(image_path, title, out_path)
    except Exception as e:
        print(f"    Thumbnail PIL render failed ({e}), falling back to plain frame")
        return _create_thumbnail_ffmpeg_fallback(image_path, out_path)


def _render_thumbnail(image_path, title, out_path):
    """Generate a 1280x720 YouTube thumbnail: scene image, a dark gradient
    panel on the left for legibility, the fixed brand headline (Cinzel Bold,
    gold gradient + glow), the per-episode title as subtitle (Lato Regular,
    all-caps), and the Narava logo bottom-left."""
    base = Image.open(image_path).convert("RGB")
    w0, h0 = base.size
    scale = max(1280 / w0, 720 / h0)
    base = base.resize((int(w0 * scale) + 1, int(h0 * scale) + 1))
    x0 = (base.width - 1280) // 2
    y0 = (base.height - 720) // 2
    base = base.crop((x0, y0, x0 + 1280, y0 + 720)).convert("RGBA")

    # Dark panel — pre-made transparent overlay (assets/shadow.png) instead of
    # a generated gradient, so the fade exactly matches the Canva reference.
    shadow_path = ASSETS_DIR / "shadow.png"
    if shadow_path.exists():
        shadow_img = Image.open(shadow_path).convert("RGBA").resize((1280, 720))
        base.alpha_composite(shadow_img)
    fade_end = int(1280 * 0.66)  # still used to confine text width to the panel

    # Text column is confined to the dark panel only — never bleed past the
    # fade edge into the photo side (this was the "memanjang satu baris" bug:
    # the headline measured its own width and ignored where the shadow ends).
    left_margin = 64
    text_max_w = fade_end - left_margin - 70

    def _wrap_pixels(text, font, max_w, tracking=0):
        tmp = Image.new("L", (1, 1))
        d = ImageDraw.Draw(tmp)
        words, lines, cur = text.split(), [], ""
        for word in words:
            trial = (cur + " " + word).strip()
            if _text_width(d, trial, font, tracking) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def _fit_wrapped(text, font_path, max_w, start_size, min_size=26, max_lines=3, tracking=0):
        size = start_size
        while size >= min_size:
            font = ImageFont.truetype(font_path, size)
            lines = _wrap_pixels(text, font, max_w, tracking)
            if len(lines) <= max_lines:
                return font, lines
            size -= 2
        font = ImageFont.truetype(font_path, min_size)
        return font, _wrap_pixels(text, font, max_w, tracking)

    # Main headline: WHITE fill + GOLD glow (fixed brand line). Starts large
    # (like the Canva reference, text filling most of the panel width) and
    # only shrinks as far as needed to stay within 3 lines.
    headline_font, headline_lines = _fit_wrapped(HEADLINE, CINZEL_BOLD, text_max_w, start_size=110, min_size=50)
    y = 58
    for line in headline_lines:
        layer, (_, lh), pad = _draw_text_layer(
            line, headline_font,
            glow_color=GOLD_TOP, solid_color=(255, 255, 255, 255),
        )
        base.alpha_composite(layer, (left_margin - pad, y - pad))
        y += lh + 6

    # Subtitle (per-episode title): gold gradient fill + a thin, tightly
    # blurred BLACK drop shadow (not a glow) for legibility, letter-spaced
    # like the reference thumbnail.
    SUBTITLE_TRACKING = 10
    subtitle_font, subtitle_lines = _fit_wrapped(
        title.upper(), LATO_REGULAR, text_max_w, start_size=44, min_size=26, tracking=SUBTITLE_TRACKING
    )
    y += 30
    for line in subtitle_lines:
        layer, (_, sh), pad = _draw_text_layer(
            line, subtitle_font,
            glow_color=(0, 0, 0), glow_blur=3, glow_alpha=0.55, glow_offset=(2, 2),
            fill_gradient=(GOLD_TOP, GOLD_BOTTOM), tracking=SUBTITLE_TRACKING,
        )
        base.alpha_composite(layer, (left_margin - pad, y - pad))
        y += sh + 12

    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_w = 220
        logo = logo.resize((logo_w, int(logo.height * logo_w / logo.width)))
        base.alpha_composite(logo, (56, 720 - logo.height - 40))

    base.convert("RGB").save(out_path, quality=95)
    return out_path


def _create_thumbnail_ffmpeg_fallback(image_path, out_path):
    """Last-resort fallback if PIL rendering fails for any reason — just a
    plain resized frame with no text, so the pipeline never hard-stops here."""
    result = subprocess.run([
        "ffmpeg", "-y", "-i", str(image_path),
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
        "-frames:v", "1", str(out_path)
        ], capture_output=True)
    return out_path


def create_video(audio_path, category, topic_id, topic_slug=None):
    images = _get_images(category, topic_slug, count=10)
    out_path = OUTPUT_DIR / "video" / f"{topic_id}.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    duration = _audio_duration(audio_path)

    # Pre-generate Ken Burns clips (smooth zoom-in only, every slide)
    # No pre-crop: our generated images are already full intentional 16:9
    # compositions, and cropdetect was misreading dark painterly backgrounds
    # as letterbox bars, cropping some images down to ~50% before the zoom
    # effect even started.
    clips_dir = out_path.parent / f"{topic_id}_clips"
    clips_dir.mkdir(exist_ok=True)

    def _clip_is_valid(path):
        # A killed background run can leave a half-written clip file behind —
        # existence alone isn't enough, it must actually probe to ~SLIDE_DURATION.
        if not path.exists() or path.stat().st_size == 0:
            return False
        try:
            return _audio_duration(path) >= SLIDE_DURATION - 1
        except subprocess.CalledProcessError:
            return False

    clip_paths = []
    for i, img in enumerate(images):
        clip_out = clips_dir / f"clip_{i:02d}.mp4"
        if not _clip_is_valid(clip_out):
            print(f"    Ken Burns clip {i+1}/{len(images)}...")
            _make_ken_burns_clip(img, clip_out)
        clip_paths.append(clip_out)

    # Build concat list — loop clips to fill audio duration
    cycle_duration = len(clip_paths) * SLIDE_DURATION
    repeats = math.ceil(duration / cycle_duration)
    concat_lines = []
    for _ in range(repeats):
        for clip in clip_paths:
            concat_lines.append(f"file '{clip.resolve()}'")
    concat_file = out_path.parent / f"{topic_id}_concat.txt"
    concat_file.write_text("\n".join(concat_lines))

    ambience_map = AMBIENCE_MAPS.get(topic_id)
    ambience_path = None
    if ambience_map:
        ambience_path = out_path.parent / f"{topic_id}_ambience.mp3"
        print(f"    Building contextual ambience ({len(ambience_map)} segments: {', '.join(n for n, _ in ambience_map)})...")
        _build_ambience_track(ambience_map, duration, ambience_path)
        music_path = ambience_path
    else:
        music_path = _get_music(category)

    if music_path:
        # aloop with a huge buffer (size=2e9) exists to repeat a SHORT static music
        # file across a long narration — it's the wrong tool for the ambience-map
        # case, where the track is already pre-built to the exact target duration.
        # Applying aloop's giant buffer to an already ~78-minute stream was crashing
        # the filter graph ("Invalid argument") partway through — drop it when the
        # ambience track is already full-length, keep it for the legacy short-loop case.
        music_filter = "volume=0.30" if ambience_map else "volume=0.30,aloop=loop=-1:size=2e+09"
        af = (
            # Force both inputs to the same sample rate/channel layout before mixing —
            # narration and music/ambience sources don't always share the same rate
            # (e.g. 48000 mono vs 44100 stereo), and amix on mismatched streams fails
            # mid-encode with "Invalid argument" rather than erroring immediately.
            "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=1.0[narration];"
            f"[2:a]aformat=sample_rates=44100:channel_layouts=stereo,{music_filter}[music];"
            "[narration][music]amix=inputs=2:duration=first:dropout_transition=3[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", str(audio_path),
            "-i", str(music_path),
            "-c:v", "copy",
            "-filter_complex", af,
            "-map", "0:v", "-map", "[aout]",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out_path),
        ]
        label = "ambience" if ambience_map else "music"
        print(f"    Assembling video + {label} ({category})...")
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out_path),
        ]
        print(f"    Assembling video (no music for {category})...")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[-600:]}")

    concat_file.unlink(missing_ok=True)
    shutil.rmtree(clips_dir)
    if ambience_path:
        ambience_path.unlink(missing_ok=True)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"    Video: {size_mb:.0f}MB, {duration/60:.0f} min → {out_path.name}")
    return out_path, images[0], duration
