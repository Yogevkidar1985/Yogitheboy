ffmpeg -v error -y -i voice_raw.wav -i music.wav -i sfx.wav -filter_complex "
[0]aresample=44100:resampler=soxr,highpass=f=85,equalizer=f=180:t=q:w=1:g=2,equalizer=f=900:t=q:w=1.2:g=-1.5,equalizer=f=3000:t=q:w=1.5:g=3,acompressor=threshold=-24dB:ratio=3:attack=5:release=90:makeup=3,loudnorm=I=-16:TP=-2:LRA=7,aecho=0.9:0.5:24:0.05,asplit=3[v][vsc][vsc2];
[1]volume=0.5[m0];[m0][vsc]sidechaincompress=threshold=0.03:ratio=5:attack=20:release=400[md];
[2]volume=0.8[s0];[s0][vsc2]sidechaincompress=threshold=0.03:ratio=4:attack=10:release=300[sd];
[v][md][sd]amix=inputs=3:normalize=0,alimiter=limit=0.89,loudnorm=I=-14:TP=-1.5:LRA=11[o]" -map "[o]" -ar 44100 -ac 2 mix.wav
