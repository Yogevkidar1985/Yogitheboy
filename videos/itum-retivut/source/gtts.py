"""Google Cloud TTS (Chirp3-HD Hebrew). API key is read from the GOOGLE_TTS_API_KEY env var only."""
import os, json, base64, urllib.request
def synth(text, out, voice='he-IL-Chirp3-HD-Charon', rate=1.0):
    key = os.environ['GOOGLE_TTS_API_KEY']
    body = {'input': {'text': text}, 'voice': {'languageCode': 'he-IL', 'name': voice},
            'audioConfig': {'audioEncoding': 'LINEAR16', 'sampleRateHertz': 24000, 'speakingRate': rate}}
    req = urllib.request.Request(f'https://texttospeech.googleapis.com/v1/text:synthesize?key={key}',
                                 data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    open(out, 'wb').write(base64.b64decode(d['audioContent']))
