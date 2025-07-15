✅ Fix Options (In Order of Precision and Feasibility)
🔧 Option 1: Use nvidia-container-toolkit with nvidia-docker Runtime
To allow container <-> GPU process mapping, you must ensure:

You're running your container with --runtime=nvidia

You have nvidia-container-toolkit installed

You're using the DCGM container with container awareness

bash
Copy
Edit
docker run --runtime=nvidia --gpus all \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /var/lib/docker/containers:/var/lib/docker/containers:ro \
  nvcr.io/nvidia/k8s/dcgm-exporter:latest
🧠 That /var/run/docker.sock + /var/lib/docker/containers volume allows the container to map PIDs to container names.

If you're not mounting both volumes, it can't resolve the process/container context—you’ll just get system-wide GPU stats.

🧬 Option 2: Use DCGM-Exporter with Custom Labels
Once you have the volumes mounted, DCGM Exporter can optionally label metrics with:

container name

image name

GPU ID

PID

To enable this:

Use the DCGM-exporter with the --collect-container-metrics flag or build with container context support

Ensure container_name, container_image labels are exposed

Then you’ll get metrics like:

text
Copy
Edit
dcgm_process_gpu_utilization{container_name="llama-container", pid="1234", gpu="0"} 72.0
You can group these in Grafana by container_name and actually see per-container GPU usage.

🛠️ Option 3: Scrape GPU Metrics via nvidia-smi + docker inspect (Custom Exporter)
This is DIY, but sometimes necessary:

Run a cron or exporter script that runs:

bash
Copy
Edit
nvidia-smi --query-compute-apps=pid,used_gpu_memory --format=csv
Then map PIDs to container names:

bash
Copy
Edit
docker inspect $(docker ps -q) | jq '.[].State.Pid'
Join them in a small script and expose as Prometheus custom metrics.

I can help you write this exporter if needed—it’s hacky but accurate when DCGM fails.

🧯 Option 4: Use gpustat in Sidecar with psutil Mapping
If you can’t modify DCGM setup:

Run a sidecar container or script with gpustat or nvidia-ml-py

Use Python to associate running PIDs with cgroups (e.g., via /proc/[pid]/cgroup)

Report metrics via a simple HTTP endpoint that Prometheus can scrape

🧱 Bonus: Consider NVIDIA DCGM with Kubernetes Plugin
If you eventually migrate to Kubernetes:

The NVIDIA device plugin for Kubernetes can expose per-pod GPU metrics by default

It natively integrates with DCGM for container labeling

You can group GPU usage by pod or namespace in Grafana

🧠 TL;DR Action Plan
Step	What to Do	Why
✅ 1	Ensure container runs with --runtime=nvidia --gpus all	Required for process ↔ GPU mapping
✅ 2	Mount /var/run/docker.sock + /var/lib/docker/containers into DCGM Exporter	Enables container context
✅ 3	Use DCGM-exporter image with container-label support	Enables container_name labels
✅ 4	Confirm dcgm_process_* metrics include container name	If not, switch build or exporter
🛠 5	If needed, write custom Prometheus exporter using nvidia-smi + docker inspect	Manual but reliable fallback