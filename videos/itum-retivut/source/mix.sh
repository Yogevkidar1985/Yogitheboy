ffmpeg -v error -y -i voice_raw.wav -i music.wav -i sfx.wav -filter_complex "
[0]aresample=44100,highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=1.5,loudnorm=I=-16:TP=-2:LRA=9,asplit=3[v][vsc][vsc2];
[1]volume=${MUSIC:-0.33}[m0];[m0][vsc]sidechaincompress=threshold=0.04:ratio=4:attack=25:release=350[md];
[2]volume=0.7[s0];[s0][vsc2]sidechaincompress=threshold=0.03:ratio=4:attack=10:release=300[sd];
[v][md][sd]amix=inputs=3:normalize=0,alimiter=limit=0.89,loudnorm=I=-14:TP=-1.5:LRA=11,apad,atrim=0:${TOTAL}[o]" -map "[o]" -ar 44100 -ac 2 mix.wav
