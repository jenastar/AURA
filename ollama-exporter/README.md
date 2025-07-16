# Ollama Prometheus Exporter

This exporter provides monitoring capabilities for Ollama through its API endpoints.

## Metrics Provided

### Availability Metrics
- `ollama_up` - Whether Ollama API is accessible (1 = up, 0 = down)
- `ollama_api_response_time_seconds` - API response time histogram
- `ollama_api_errors_total` - Counter of API errors

### Model Metrics
- `ollama_model_count` - Number of models available
- `ollama_model_size_bytes` - Size of each model in bytes
- `ollama_model_info` - Model information labels (family, parameter_size, quantization)

### Inference Detection Metrics
- `ollama_inference_active` - Whether inference is currently active (heuristic)
- `ollama_gpu_likely_active` - Likelihood that GPU is being used (0-1)
- `ollama_inference_requests_total` - Total inference requests detected
- `ollama_last_inference_timestamp` - Timestamp of last detected inference

## How It Works

Since Ollama doesn't provide a `/api/status` endpoint, this exporter uses several heuristics:

1. **API Responsiveness** - Monitors `/api/tags` endpoint response times
2. **Inference Detection** - Attempts to detect when Ollama is busy processing
3. **Model Tracking** - Tracks available models and their sizes

## Configuration

Environment variables:
- `OLLAMA_HOST` - Ollama hostname (default: ollama)
- `OLLAMA_PORT` - Ollama port (default: 11434)
- `EXPORTER_PORT` - Port for metrics endpoint (default: 9200)
- `SCRAPE_INTERVAL` - How often to collect metrics (default: 15s)

## Usage

### Docker Compose

```yaml
ollama_exporter:
  build: ./ollama-exporter
  environment:
    - OLLAMA_HOST=ollama
    - OLLAMA_PORT=11434
  ports:
    - "9200:9200"
```

### Prometheus Configuration

```yaml
- job_name: 'ollama'
  static_configs:
    - targets: ['ollama_exporter:9200']
```

## Limitations

- Cannot directly detect GPU usage - uses inference heuristics
- Requires Ollama API to be accessible
- Inference detection is based on API response patterns

## Future Improvements

When Ollama implements the proposed `/metrics` endpoint (https://github.com/ollama/ollama/issues/3144), this exporter can be updated to use official metrics including:
- GPU utilization
- Memory utilization  
- CPU utilization
- Request counts and latencies