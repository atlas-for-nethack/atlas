"""Size the generated branch-stair study without repainting its pixels."""
from pathlib import Path
import hashlib
import json
from PIL import Image

HERE = Path(__file__).resolve().parent
source = HERE / 'branch-up-source-v2.png'
image = Image.open(source).convert('RGBA')
# Alpha-one specks extend far beyond the actual sprite; discard only those
# effectively invisible pixels before calculating the subject's bounds.
image.putalpha(image.getchannel('A').point(lambda value: 0 if value <= 2 else value))
bounds = image.getchannel('A').getbbox()
subject = image.crop(bounds)
scale = min(48 / subject.width, 60 / subject.height)
size = (round(subject.width * scale), round(subject.height * scale))
sprite = Image.new('RGBA', (64, 64))
sprite.alpha_composite(subject.resize(size, Image.Resampling.NEAREST),
                       ((64-size[0])//2, 62-size[1]))
sprite.save(HERE / 'branch-up.png')
record = {
    'status': 'approved September 24, 2026; integrated as branch staircase up',
    'origin': 'original-ai-generated', 'tool': 'image_gen',
    'source': source.name,
    'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'upReference': {'file': 'regular-up-reference.png',
                    'sha256': hashlib.sha256((HERE/'regular-up-reference.png').read_bytes()).hexdigest()},
    'prompt': 'PROMPTS.md', 'alphaCleanup': 'alpha <= 2 becomes 0',
    'cropBounds': bounds, 'renderedSize': size, 'tileSize': [64, 64],
    'resampling': 'nearest neighbor, no RGB repainting',
    'output': 'branch-up.png',
    'outputSha256': hashlib.sha256((HERE/'branch-up.png').read_bytes()).hexdigest(),
    'artworkLicense': 'CC-BY-4.0',
    'artworkCredit': 'NetHack Atlas project'
}
(HERE/'provenance.json').write_text(json.dumps(record, indent=2)+'\n')
print(f'Prepared {size} subject in 64x64 cell from {bounds}')
