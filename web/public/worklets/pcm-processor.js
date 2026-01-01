// AudioWorkletProcessor: PCM float32 -> main thread'e gönder
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0] && input[0].length) {
      // Float32Array'i main thread'e gönder
      this.port.postMessage(input[0]);
    }
    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);

