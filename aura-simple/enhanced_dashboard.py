#!/usr/bin/env python3
"""
Enhanced AURA Dashboard with Grafana-like functionality
"""

import os
import time
import json
import collections
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, Response

# Historical data storage (in-memory for now)
class HistoricalData:
    def __init__(self, max_points=300):  # 5 minutes at 1 second intervals
        self.max_points = max_points
        self.data = collections.defaultdict(lambda: collections.deque(maxlen=max_points))
        self.timestamps = collections.deque(maxlen=max_points)
        
    def add_data_point(self, metrics_data):
        timestamp = time.time() * 1000  # JavaScript timestamp
        self.timestamps.append(timestamp)
        
        # System metrics
        if 'system' in metrics_data:
            sys = metrics_data['system']
            self.data['cpu_percent'].append(sys.get('cpu_percent', 0))
            self.data['memory_percent'].append(sys.get('memory', {}).get('percent', 0))
            self.data['load_1m'].append(sys.get('load', {}).get('1m', 0))
            self.data['load_5m'].append(sys.get('load', {}).get('5m', 0))
            self.data['load_15m'].append(sys.get('load', {}).get('15m', 0))
            
        # GPU metrics
        if 'gpu' in metrics_data and metrics_data['gpu']:
            for gpu in metrics_data['gpu']:
                gpu_idx = gpu['index']
                self.data[f'gpu_{gpu_idx}_utilization'].append(gpu.get('utilization', 0))
                self.data[f'gpu_{gpu_idx}_memory_percent'].append(
                    (gpu.get('memory_used', 0) / gpu.get('memory_total', 1)) * 100 if gpu.get('memory_total', 0) > 0 else 0
                )
                self.data[f'gpu_{gpu_idx}_temperature'].append(gpu.get('temperature', 0))
                self.data[f'gpu_{gpu_idx}_power'].append(gpu.get('power', 0))
                
        # Docker metrics
        if 'docker' in metrics_data:
            total_containers = len(metrics_data['docker'])
            running_containers = sum(1 for c in metrics_data['docker'] if c['status'] == 'running')
            self.data['total_containers'].append(total_containers)
            self.data['running_containers'].append(running_containers)
            
            # Individual container metrics
            for container in metrics_data['docker']:
                name = container['name']
                self.data[f'container_{name}_cpu'].append(container.get('cpu_percent', 0))
                self.data[f'container_{name}_memory_mb'].append(container.get('memory_usage', 0) / 1024 / 1024)
                
    def get_time_series(self, metric_name, time_range_minutes=5):
        now = time.time() * 1000
        cutoff = now - (time_range_minutes * 60 * 1000)
        
        data_points = []
        timestamps = list(self.timestamps)
        values = list(self.data[metric_name])
        
        for i, ts in enumerate(timestamps):
            if ts >= cutoff and i < len(values):
                data_points.append({'x': ts, 'y': values[i]})
                
        return data_points
    
    def get_latest_value(self, metric_name):
        values = self.data[metric_name]
        return values[-1] if values else 0

# Global historical data store
historical_data = HistoricalData()

# Enhanced HTML dashboard with Chart.js
ENHANCED_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AURA Enhanced Monitoring Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 0; 
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #fff;
        }
        .header { 
            background: rgba(0,0,0,0.3); 
            padding: 20px; 
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .header h1 { 
            margin: 0; 
            font-size: 2.5em; 
            font-weight: 300;
        }
        .header .subtitle { 
            opacity: 0.8; 
            margin: 5px 0; 
        }
        .controls {
            margin: 20px 0;
            display: flex;
            gap: 15px;
            align-items: center;
        }
        .time-range-btn {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .time-range-btn:hover, .time-range-btn.active {
            background: rgba(255,255,255,0.2);
            border-color: rgba(255,255,255,0.5);
        }
        .refresh-btn {
            background: linear-gradient(45deg, #00c851, #007e33);
            border: none;
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.2s ease;
        }
        .refresh-btn:hover {
            transform: scale(1.05);
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            padding: 20px;
        }
        .panel {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .panel h3 {
            margin-top: 0;
            font-size: 1.3em;
            font-weight: 400;
            border-bottom: 1px solid rgba(255,255,255,0.2);
            padding-bottom: 10px;
        }
        .chart-container {
            position: relative;
            height: 300px;
            margin: 15px 0;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            margin: 5px 0;
        }
        .stat-label {
            font-size: 0.9em;
            opacity: 0.8;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-up { background: #00c851; }
        .status-down { background: #ff4444; }
        .status-warning { background: #ffbb33; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            padding: 12px 8px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            background: rgba(255,255,255,0.1);
            font-weight: 500;
        }
        .gpu-panel { border-left: 4px solid #ff6b6b; }
        .system-panel { border-left: 4px solid #4ecdc4; }
        .docker-panel { border-left: 4px solid #45b7d1; }
        .services-panel { border-left: 4px solid #96ceb4; }
        
        @media (max-width: 768px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
                padding: 10px;
            }
            .controls {
                flex-direction: column;
                align-items: stretch;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 AURA Enhanced Dashboard</h1>
        <p class="subtitle">Real-time monitoring with historical charts and interactive panels</p>
        <div class="controls">
            <button class="time-range-btn active" onclick="setTimeRange(1)">1m</button>
            <button class="time-range-btn" onclick="setTimeRange(5)">5m</button>
            <button class="time-range-btn" onclick="setTimeRange(15)">15m</button>
            <button class="time-range-btn" onclick="setTimeRange(60)">1h</button>
            <button class="refresh-btn" onclick="refreshData()">🔄 Refresh</button>
            <span style="margin-left: auto; opacity: 0.8;">Last Update: <span id="last-update">{{ last_update or 'Never' }}</span></span>
        </div>
    </div>
    
    <div class="dashboard-grid">
        <!-- System Overview Panel -->
        <div class="panel system-panel">
            <h3>💻 System Overview</h3>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="cpu-percent">{{ "%.1f"|format(system.cpu_percent if system else 0) }}%</div>
                    <div class="stat-label">CPU Usage</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="memory-percent">{{ "%.1f"|format(system.memory.percent if system else 0) }}%</div>
                    <div class="stat-label">Memory Usage</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="load-1m">{{ "%.2f"|format(system.load['1m'] if system else 0) }}</div>
                    <div class="stat-label">Load 1m</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="uptime-hours">{{ "%.1f"|format((system.uptime / 3600) if system else 0) }}h</div>
                    <div class="stat-label">Uptime</div>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="cpuChart"></canvas>
            </div>
        </div>

        <!-- Memory & Load Panel -->
        <div class="panel system-panel">
            <h3>📊 Memory & Load Averages</h3>
            <div class="chart-container">
                <canvas id="memoryChart"></canvas>
            </div>
        </div>

        <!-- GPU Monitoring Panel -->
        <div class="panel gpu-panel">
            <h3>🎮 GPU Performance</h3>
            {% if gpu and gpu|length > 0 %}
            <div class="stats-grid">
                {% for g in gpu %}
                <div class="stat-card">
                    <div class="stat-value">{{ g.utilization }}%</div>
                    <div class="stat-label">GPU {{ g.index }} Util</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ "%.1f"|format(g.memory_used / 1024**3) }}GB</div>
                    <div class="stat-label">GPU {{ g.index }} Memory</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ g.temperature }}°C</div>
                    <div class="stat-label">Temperature</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ "%.1f"|format(g.power) }}W</div>
                    <div class="stat-label">Power</div>
                </div>
                {% endfor %}
            </div>
            <div class="chart-container">
                <canvas id="gpuChart"></canvas>
            </div>
            {% else %}
            <p>No GPU available or data unavailable</p>
            {% endif %}
        </div>

        <!-- GPU Memory & Inference Panel -->
        <div class="panel gpu-panel">
            <h3>🔍 GPU Memory & Inference Detection</h3>
            {% if gpu and gpu|length > 0 %}
            {% for g in gpu %}
            <div style="margin-bottom: 20px;">
                <h4>GPU {{ g.index }}</h4>
                {% if g.inference_active %}
                <div style="background: rgba(255,107,107,0.2); padding: 10px; border-radius: 8px; margin: 10px 0;">
                    <span class="status-indicator status-up"></span>
                    <strong>Inference Detected!</strong> Unknown GPU usage: {{ "%.1f"|format(g.memory_unknown / 1024**3) }} GB
                </div>
                {% endif %}
                <div class="chart-container">
                    <canvas id="gpuMemoryChart{{ g.index }}"></canvas>
                </div>
            </div>
            {% endfor %}
            {% endif %}
        </div>

        <!-- Docker Containers Panel -->
        <div class="panel docker-panel">
            <h3>🐳 Docker Containers</h3>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="total-containers">{{ (docker|length) if docker else 0 }}</div>
                    <div class="stat-label">Total Containers</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="running-containers">{{ docker|selectattr('status', 'equalto', 'running')|list|length if docker else 0 }}</div>
                    <div class="stat-label">Running</div>
                </div>
            </div>
            {% if docker %}
            <div class="chart-container">
                <canvas id="dockerChart"></canvas>
            </div>
            <table>
                <tr><th>Container</th><th>Status</th><th>CPU</th><th>Memory</th><th>Project</th></tr>
                {% for c in docker %}
                <tr>
                    <td>{{ c.name }}</td>
                    <td>
                        <span class="status-indicator {% if c.status == 'running' %}status-up{% else %}status-down{% endif %}"></span>
                        {{ c.status }}
                    </td>
                    <td>{{ "%.1f"|format(c.cpu_percent) }}%</td>
                    <td>{{ "%.0f"|format(c.memory_usage / 1024**2) }} MB</td>
                    <td>{{ c.project }}</td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <p>No containers running or Docker unavailable</p>
            {% endif %}
        </div>

        <!-- External Services Panel -->
        <div class="panel services-panel">
            <h3>🔗 External Services Health</h3>
            {% if services %}
            <div class="stats-grid">
                {% for s in services %}
                <div class="stat-card">
                    <div class="stat-value">
                        <span class="status-indicator {% if s.status == 'up' %}status-up{% else %}status-down{% endif %}"></span>
                        {{ s.status.upper() }}
                    </div>
                    <div class="stat-label">{{ s.name.replace('vector_db_', '') }}</div>
                    {% if s.response_time %}
                    <div style="font-size: 0.8em; opacity: 0.7;">{{ (s.response_time * 1000)|round(0)|int }}ms</div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            <div class="chart-container">
                <canvas id="servicesChart"></canvas>
            </div>
            {% else %}
            <p>No external services configured</p>
            {% endif %}
        </div>
    </div>

    <script>
        let currentTimeRange = 1; // minutes
        let charts = {};
        
        // Chart.js default configuration
        Chart.defaults.color = '#ffffff';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
        
        function setTimeRange(minutes) {
            currentTimeRange = minutes;
            document.querySelectorAll('.time-range-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            refreshCharts();
        }
        
        function refreshData() {
            location.reload();
        }
        
        async function fetchTimeSeriesData(metric, timeRange) {
            try {
                const response = await fetch(`/api/timeseries/${metric}?range=${timeRange}`);
                return await response.json();
            } catch (error) {
                console.error('Error fetching time series data:', error);
                return [];
            }
        }
        
        async function initializeCharts() {
            // CPU Chart
            const cpuCtx = document.getElementById('cpuChart').getContext('2d');
            charts.cpu = new Chart(cpuCtx, {
                type: 'line',
                data: {
                    datasets: [{
                        label: 'CPU Usage %',
                        borderColor: '#ff6b6b',
                        backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: { unit: 'second' }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: { callback: function(value) { return value + '%'; } }
                        }
                    },
                    plugins: {
                        legend: { display: true }
                    }
                }
            });

            // Memory Chart
            const memoryCtx = document.getElementById('memoryChart').getContext('2d');
            charts.memory = new Chart(memoryCtx, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: 'Memory Usage %',
                            borderColor: '#4ecdc4',
                            backgroundColor: 'rgba(78, 205, 196, 0.1)',
                            tension: 0.4,
                            fill: true
                        },
                        {
                            label: 'Load 1m',
                            borderColor: '#45b7d1',
                            backgroundColor: 'rgba(69, 183, 209, 0.1)',
                            tension: 0.4,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: { unit: 'second' }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            position: 'left',
                            ticks: { callback: function(value) { return value + '%'; } }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            grid: { drawOnChartArea: false },
                            ticks: { callback: function(value) { return value.toFixed(2); } }
                        }
                    }
                }
            });

            // GPU Chart (if GPU available)
            const gpuCanvas = document.getElementById('gpuChart');
            if (gpuCanvas) {
                const gpuCtx = gpuCanvas.getContext('2d');
                charts.gpu = new Chart(gpuCtx, {
                    type: 'line',
                    data: {
                        datasets: [
                            {
                                label: 'GPU Utilization %',
                                borderColor: '#ff6b6b',
                                backgroundColor: 'rgba(255, 107, 107, 0.1)',
                                tension: 0.4
                            },
                            {
                                label: 'GPU Temperature °C',
                                borderColor: '#ffbb33',
                                backgroundColor: 'rgba(255, 187, 51, 0.1)',
                                tension: 0.4,
                                yAxisID: 'y1'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: {
                                type: 'time',
                                time: { unit: 'second' }
                            },
                            y: {
                                beginAtZero: true,
                                max: 100,
                                position: 'left'
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                grid: { drawOnChartArea: false }
                            }
                        }
                    }
                });
            }

            // Load initial data
            refreshCharts();
        }
        
        async function refreshCharts() {
            // Update CPU chart
            const cpuData = await fetchTimeSeriesData('cpu_percent', currentTimeRange);
            if (charts.cpu && cpuData.length > 0) {
                charts.cpu.data.datasets[0].data = cpuData;
                charts.cpu.update('none');
            }

            // Update Memory chart
            const memoryData = await fetchTimeSeriesData('memory_percent', currentTimeRange);
            const loadData = await fetchTimeSeriesData('load_1m', currentTimeRange);
            if (charts.memory) {
                if (memoryData.length > 0) {
                    charts.memory.data.datasets[0].data = memoryData;
                }
                if (loadData.length > 0) {
                    charts.memory.data.datasets[1].data = loadData;
                }
                charts.memory.update('none');
            }

            // Update GPU chart
            if (charts.gpu) {
                const gpuUtilData = await fetchTimeSeriesData('gpu_0_utilization', currentTimeRange);
                const gpuTempData = await fetchTimeSeriesData('gpu_0_temperature', currentTimeRange);
                if (gpuUtilData.length > 0) {
                    charts.gpu.data.datasets[0].data = gpuUtilData;
                }
                if (gpuTempData.length > 0) {
                    charts.gpu.data.datasets[1].data = gpuTempData;
                }
                charts.gpu.update('none');
            }
        }
        
        // Initialize charts when page loads
        document.addEventListener('DOMContentLoaded', function() {
            initializeCharts();
            
            // Auto-refresh every 30 seconds
            setInterval(refreshCharts, 30000);
        });
    </script>
</body>
</html>
"""

def create_enhanced_dashboard_routes(app, metrics_data, historical_data):
    """Add enhanced dashboard routes to Flask app"""
    
    @app.route('/')
    def enhanced_dashboard():
        """Enhanced dashboard with charts"""
        return render_template_string(ENHANCED_DASHBOARD_HTML, 
                                    system=metrics_data.get('system'),
                                    docker=metrics_data.get('docker'),
                                    gpu=metrics_data.get('gpu'),
                                    services=metrics_data.get('services'),
                                    last_update=metrics_data.get('last_update'))
    
    @app.route('/api/timeseries/<metric>')
    def get_timeseries(metric):
        """Get time series data for charts"""
        time_range = int(request.args.get('range', 5))  # minutes
        data = historical_data.get_time_series(metric, time_range)
        return jsonify(data)
    
    @app.route('/simple')
    def simple_dashboard():
        """Original simple dashboard"""
        return render_template_string("""
        <h1>Simple Dashboard</h1>
        <p>This is the original simple dashboard. <a href="/">Go to Enhanced Dashboard</a></p>
        <pre>{{ data }}</pre>
        """, data=json.dumps(metrics_data, indent=2, default=str))

# Function to update historical data
def update_historical_data(metrics_data_dict, historical_data_obj):
    """Update historical data storage"""
    historical_data_obj.add_data_point(metrics_data_dict)