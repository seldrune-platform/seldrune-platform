class SeldruneSeedWarmth extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [{
      name: 'warmth',
      defaultValue: 0.2,
      minValue: 0,
      maxValue: 1,
      automationRate: 'k-rate',
    }];
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    const output = outputs[0];
    if (!output || !output.length) return true;
    const warmth = parameters.warmth && parameters.warmth.length ? parameters.warmth[0] : 0.2;
    const drive = 1 + warmth * 2.5;
    const normalizer = Math.tanh(drive);
    for (let channel = 0; channel < output.length; channel += 1) {
      const source = input && input[Math.min(channel, input.length - 1)];
      const destination = output[channel];
      if (!source) {
        destination.fill(0);
        continue;
      }
      for (let index = 0; index < destination.length; index += 1) {
        destination[index] = Math.tanh(source[index] * drive) / normalizer;
      }
    }
    return true;
  }
}

registerProcessor('seldrune-seed-warmth', SeldruneSeedWarmth);
