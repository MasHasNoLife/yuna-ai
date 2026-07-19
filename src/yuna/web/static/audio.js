// Audio: PCM playback (scheduled AudioBuffers) + push-to-talk recording.

export class PcmPlayer {
  constructor(visualizerCanvas) {
    this.ctx = null;
    this.sampleRate = 24000;
    this.nextTime = 0;
    this.carry = null; // trailing odd byte held over between chunks
    this.canvas = visualizerCanvas;
    this.vctx = visualizerCanvas ? visualizerCanvas.getContext("2d") : null;
  }

  start(sampleRate) {
    if (!this.ctx)
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (this.ctx.state === "suspended") this.ctx.resume();
    this.sampleRate = sampleRate;
    this.carry = null; // fresh utterance — drop any stray byte from the last one
    this.nextTime = Math.max(this.ctx.currentTime + 0.05, this.nextTime);
  }

  // 16-bit little-endian mono PCM. Streamed chunks arrive at arbitrary byte
  // boundaries, so a chunk may end mid-sample; we carry that leftover byte to
  // the next chunk. Decoding each chunk independently would misalign every
  // sample after the first odd-length chunk and play as noise.
  feed(arrayBuffer) {
    if (!this.ctx) return;
    let bytes = new Uint8Array(arrayBuffer);
    if (this.carry) {
      const merged = new Uint8Array(this.carry.length + bytes.length);
      merged.set(this.carry);
      merged.set(bytes, this.carry.length);
      bytes = merged;
      this.carry = null;
    }
    const usable = bytes.length - (bytes.length % 2);
    if (usable < bytes.length) this.carry = bytes.slice(usable);
    if (usable < 2) return;
    const int16 = new Int16Array(usable / 2);
    new Uint8Array(int16.buffer).set(bytes.subarray(0, usable));
    const float32 = new Float32Array(int16.length);
    let peak = 0;
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
      const a = Math.abs(float32[i]);
      if (a > peak) peak = a;
    }
    const buf = this.ctx.createBuffer(1, float32.length, this.sampleRate);
    buf.getChannelData(0).set(float32);
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.ctx.destination);
    if (this.nextTime < this.ctx.currentTime)
      this.nextTime = this.ctx.currentTime + 0.02;
    src.start(this.nextTime);
    this.nextTime += buf.duration;
    this.drawLevel(peak);
  }

  drawLevel(peak) {
    if (!this.vctx) return;
    const { width: w, height: h } = this.canvas;
    this.vctx.fillStyle = "#0d1117";
    this.vctx.fillRect(0, 0, w, h);
    this.vctx.fillStyle = "#59c2ff";
    this.vctx.fillRect(0, h / 2 - (h * peak) / 2, w * peak, h * peak || 1);
  }

  stopVisualizer() {
    if (this.vctx) setTimeout(() => this.drawLevel(0), 300);
  }
}

export class Recorder {
  constructor() {
    this.mediaRecorder = null;
    this.chunks = [];
  }

  async start() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.chunks = [];
    this.mediaRecorder = new MediaRecorder(stream);
    this.mediaRecorder.ondataavailable = (e) =>
      e.data.size && this.chunks.push(e.data);
    this.mediaRecorder.start();
  }

  stop() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder) return resolve(null);
      this.mediaRecorder.onstop = () => {
        this.mediaRecorder.stream.getTracks().forEach((t) => t.stop());
        resolve(new Blob(this.chunks, { type: this.mediaRecorder.mimeType }));
      };
      this.mediaRecorder.stop();
    });
  }
}
