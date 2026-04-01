#!/usr/bin/env python3
"""
make_gif.py — Capture scrolling screenshots of the HTML report and stitch into a GIF.
Usage: python make_gif.py [report.html] [output.gif]
"""
import sys
import asyncio
import glob as _glob
from pathlib import Path
from PIL import Image
import io

def _latest_report() -> Path:
    """Return the most recently modified report_*.html in the script's directory."""
    candidates = sorted(
        Path(__file__).parent.glob("report_*.html"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "No report_*.html found in the current directory. "
        "Pass an explicit path: python make_gif.py <report.html>"
    )

OUTPUT_GIF  = Path(__file__).parent / "docs" / "images" / "sample-report.gif"

# GIF settings
VIEWPORT_W  = 900
VIEWPORT_H  = 700       # visible window height
SCROLL_STEP = 620       # pixels to scroll each frame (slight overlap for context)
FRAME_MS    = 1800      # ms per frame in GIF
PAUSE_MS    = 3000      # longer pause on first and last frame
GIF_WIDTH   = 700       # resize to this width for README


async def capture_frames(html_path: Path) -> list:
    from playwright.async_api import async_playwright

    frames = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": VIEWPORT_W, "height": VIEWPORT_H})
        await page.goto(html_path.as_uri())
        await page.wait_for_load_state("networkidle")

        # Get full page height
        total_height = await page.evaluate("document.body.scrollHeight")
        scroll_y = 0

        print(f"  Page height: {total_height}px — capturing frames...")
        while True:
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await asyncio.sleep(0.15)   # let scroll settle

            png = await page.screenshot(type="png")
            img = Image.open(io.BytesIO(png)).convert("RGB")

            # Resize to GIF_WIDTH preserving aspect ratio
            scale = GIF_WIDTH / img.width
            new_h = int(img.height * scale)
            img = img.resize((GIF_WIDTH, new_h), Image.LANCZOS)
            frames.append(img)
            print(f"  Frame {len(frames):2d}  scroll_y={scroll_y}")

            if scroll_y + VIEWPORT_H >= total_height:
                break
            scroll_y = min(scroll_y + SCROLL_STEP, total_height - VIEWPORT_H)

        await browser.close()

    return frames


def save_gif(frames: list, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)

    durations = []
    for i, _ in enumerate(frames):
        if i == 0 or i == len(frames) - 1:
            durations.append(PAUSE_MS)
        else:
            durations.append(FRAME_MS)

    # Convert to palette mode for smaller GIF
    palette_frames = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for f in frames]

    palette_frames[0].save(
        output,
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    size_kb = output.stat().st_size // 1024
    print(f"\n  Saved: {output}  ({size_kb} KB, {len(frames)} frames)")


async def main():
    try:
        html_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _latest_report()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    out_path  = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_GIF

    if not html_path.exists():
        print(f"ERROR: {html_path} not found.")
        sys.exit(1)

    print(f"Capturing: {html_path.name}")
    frames = await capture_frames(html_path)
    print(f"Stitching {len(frames)} frames into GIF...")
    save_gif(frames, out_path)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
