import subprocess, json, os
# id, src start, src end, speed
SHOTS = [
 ('view',    20.0, 23.4, 1.30),
 ('living',  0.0,  2.4,  1.15),
 ('dining',  3.9,  5.3,  1.10),
 ('kitchen', 28.4, 32.6, 1.55),
 ('balcony', 14.9, 17.8, 1.35),
 ('sunset',  23.6, 25.1, 1.00),
 ('master',  57.0, 59.9, 1.35),
 ('closet',  60.0, 61.6, 1.00),
 ('kids',    53.1, 55.7, 1.35),
 ('room3',   67.0, 69.9, 1.45),
 ('bath',    47.1, 48.8, 1.05),
 ('laundry', 37.0, 39.2, 1.25),
 ('hall',    42.0, 44.6, 1.00),
]
meta = {}
for sid, s, e, k in SHOTS:
    d = f'www/f/{sid}'; os.makedirs(d, exist_ok=True)
    for fn in os.listdir(d): os.remove(os.path.join(d, fn))
    vf = (f"setpts=PTS/{k},fps=30,scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,"
          "eq=contrast=1.08:saturation=1.10:brightness=0.015:gamma=0.98,colorbalance=rs=0.03:bs=-0.03:rh=0.02:bh=-0.02,unsharp=5:5:0.9")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(s), '-t', str(e - s), '-i', 'v2.mp4', '-vf', vf, '-q:v', '3', f'{d}/%04d.jpg'], check=True)
    meta[sid] = len(os.listdir(d))
json.dump(meta, open('www/frames.json', 'w'))
print(meta)
