# GPU Memory Inference Exporter

This exporter implements a novel approach to detect GPU usage by containers that don't appear in nvidia-smi process lists (like Ollama).

## Algorithm

1. **Gather Total GPU Usage**: Uses pynvml to get total GPU memory used
2. **Enumerate Known Processes**: Uses nvidia-smi to get all visible GPU processes
3. **Map PIDs to Containers**: Checks `/proc/<pid>/cgroup` to map processes to containers
4. **Calculate Delta**: `Unknown = Total - Known`
5. **Assign to Containers**: Distributes unknown memory to containers with GPU access but no visible processes

## Metrics Provided

### GPU Metrics
- `gpu_memory_total_bytes` - Total GPU memory
- `gpu_memory_used_bytes` - Used GPU memory (total)
- `gpu_memory_free_bytes` - Free GPU memory
- `gpu_memory_known_bytes` - Memory used by known processes
- `gpu_memory_unknown_bytes` - Memory used by unknown processes (delta)

### Container Metrics
- `container_gpu_memory_bytes` - GPU memory per container with labels:
  - `method`: "nvidia-smi" (known) or "inference" (calculated)
  - `container_name`, `container_id`, `gpu`
- `container_gpu_detected` - Whether container has GPU access
- `gpu_inference_active` - Whether unknown GPU usage was detected

## How It Works

```
Total GPU Memory Used: 10GB
├── Known (nvidia-smi visible): 2GB
│   └── container-A: 2GB
└── Unknown (delta): 8GB
    └── Inferred for Ollama: 8GB
```

## Requirements

- NVIDIA GPU with drivers
- nvidia-container-toolkit
- Docker socket access
- Host PID namespace access (for process mapping)

## Configuration

Environment variables:
- `EXPORTER_PORT` - Metrics port (default: 9201)
- `SCRAPE_INTERVAL` - Collection interval in seconds (default: 10)

## Usage

```bash
docker run --runtime=nvidia \
  --gpus all \
  --privileged \
  --pid=host \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /proc:/host/proc:ro \
  -p 9201:9201 \
  gpu-inference-exporter
```

## Example Metrics

```
# Total GPU memory
gpu_memory_used_bytes{gpu="0"} 10737418240

# Known process memory
gpu_memory_known_bytes{gpu="0"} 2147483648

# Unknown memory (delta)
gpu_memory_unknown_bytes{gpu="0"} 8589934592

# Inferred container usage
container_gpu_memory_bytes{container_name="ollama",gpu="0",method="inference"} 8589934592
```

## Limitations

- Assumes unknown memory belongs to containers with GPU access
- Simple equal distribution among unknown containers
- Requires privileged access for process inspection

## Advantages

- Detects "invisible" GPU workloads like Ollama
- No modification to monitored containers required
- Works with existing monitoring infrastructure