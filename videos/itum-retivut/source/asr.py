import sys, sherpa_onnx, soundfile as sf, numpy as np, subprocess, json
D='/tmp/asr/sherpa-onnx-whisper-turbo/'
import glob
enc=glob.glob(D+'*encoder.int8.onnx') or glob.glob(D+'*encoder.onnx'); dec=glob.glob(D+'*decoder.int8.onnx') or glob.glob(D+'*decoder.onnx')
rec=sherpa_onnx.OfflineRecognizer.from_whisper(encoder=enc[0],decoder=dec[0],tokens=glob.glob(D+'*tokens.txt')[0],language='he',task='transcribe',num_threads=8)
def tx(path):
    subprocess.run(['ffmpeg','-v','error','-y','-i',path,'-ar','16000','-ac','1','/tmp/asr_in.wav'],check=True)
    a,sr=sf.read('/tmp/asr_in.wav',dtype='float32')
    s=rec.create_stream(); s.accept_waveform(sr,a); rec.decode_stream(s); return s.result.text.strip()
if __name__=='__main__':
    for p in sys.argv[1:]: print(p,'=>',tx(p))
