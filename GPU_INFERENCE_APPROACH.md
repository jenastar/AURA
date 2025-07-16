# GPU Memory Inference Approach

## Overview

This branch implements a novel GPU memory inference method to detect "invisible" GPU workloads like Ollama that don't appear in nvidia-smi process listings.

## The Problem

Modern ML frameworks (Ollama, LLMs) allocate GPU memory in ways that bypass traditional monitoring:
- Memory is allocated but no process appears in nvidia-smi
- Standard tools report memory as "used" but can't attribute it to any process
- Container-level GPU monitoring becomes impossible

## The Solution: Memory Delta Inference

### Algorithm

```
1. Total GPU Memory = Get actual GPU memory usage (via NVML)
2. Known Memory = Sum of all visible processes (via nvidia-smi)
3. Unknown Memory = Total - Known
4. Inference = Assign unknown memory to containers with GPU access
```

### Example

```
GPU Memory Status:
├── Total Used: 10 GB
├── Known Processes: 2 GB
│   └── Container A (pytorch): 2 GB
└── Unknown (Delta): 8 GB
    └── Inferred → Ollama Container: 8 GB
```

## Implementation

### Basic Version (`gpu_inference_exporter.py`)
- Simple delta calculation
- Equal distribution among unknown containers
- Basic container detection

### Enhanced Version (`enhanced_gpu_inference.py`)
- Weighted distribution based on:
  - Container name patterns (LLM indicators)
  - Historical GPU usage patterns
  - Container runtime configuration
- Confidence scoring
- Profile tracking for better inference

## Metrics Exposed

```prometheus
# GPU Memory Breakdown
gpu_memory_total_bytes{gpu="0"} 12884901888
gpu_memory_used_bytes{gpu="0"} 10737418240
gpu_memory_known_bytes{gpu="0"} 2147483648
gpu_memory_unknown_bytes{gpu="0"} 8589934592

# Container Attribution
container_gpu_memory_bytes{container_name="ollama",method="inference",gpu="0"} 8589934592
container_gpu_memory_bytes{container_name="pytorch",method="nvidia-smi",gpu="0"} 2147483648

# Inference Confidence
gpu_inference_confidence{gpu="0"} 0.85
container_gpu_score{container_name="ollama"} 0.9
```

## Deployment

```yaml
gpu_inference_exporter:
  build: ./gpu-inference-exporter
  runtime: nvidia
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - /proc:/host/proc:ro
  ports:
    - "9201:9201"
  privileged: true
  pid: host
```

## Testing

```bash
# Build and run
docker compose up -d gpu_inference_exporter

# Check metrics
curl localhost:9201/metrics | grep container_gpu_memory_bytes

# Run test script
./gpu-inference-exporter/test_inference.sh
```

## Advantages

1. **Detects Invisible Workloads**: Finally catches Ollama and similar GPU usage
2. **No Container Modification**: Works with existing containers
3. **Confidence Scoring**: Provides reliability metrics
4. **Historical Learning**: Improves accuracy over time

## Limitations

1. **Attribution Accuracy**: When multiple unknown containers exist, distribution is estimated
2. **Requires Privileges**: Needs host PID namespace and Docker socket access
3. **Inference-based**: Not as accurate as direct measurement

## Comparison with Previous Approaches

| Approach | Can Detect Ollama | Accuracy | Complexity |
|----------|------------------|----------|------------|
| nvidia-smi | ❌ | High | Low |
| eBPF | ❌ (failed) | - | Very High |
| API Monitoring | ❌ | Low | Medium |
| **Memory Inference** | ✅ | Medium | Medium |

## Future Improvements

1. **Machine Learning**: Use ML to predict container GPU usage patterns
2. **Correlation**: Correlate with CPU/network activity for better attribution
3. **NVML Events**: If NVML adds memory allocation events, integrate them
4. **Kernel Module**: Custom kernel module for precise tracking (requires native Linux)

## Conclusion

While not perfect, this memory inference approach is currently the **only working method** to detect Ollama and similar "invisible" GPU workloads in containerized environments.