#!/usr/bin/env python3
"""
Ollama Inference Wrapper with Metrics
This wrapper intercepts Ollama API calls to track detailed metrics
"""

import os
import json
import time
import uuid
import asyncio
import aiohttp
from typing import Dict, Any, Optional, AsyncIterator
from aiohttp import web
from prometheus_client import start_http_server
from llm_metrics_exporter import (
    tokens_generated_total,
    prompt_tokens_total,
    response_tokens_total,
    inference_latency,
    tokens_per_second,
    active_requests,
    model_load_time,
    inference_errors,
    queue_size,
    RequestTracker
)


class OllamaInferenceWrapper:
    """Proxy wrapper for Ollama that tracks detailed metrics"""
    
    def __init__(self, ollama_host: str, ollama_port: int, metrics_port: int):
        self.ollama_base = f"http://{ollama_host}:{ollama_port}"
        self.metrics_port = metrics_port
        self.tracker = RequestTracker()
        self.container_name = os.environ.get('CONTAINER_NAME', 'ollama-wrapper')
        self.pending_requests = []
        self.model_load_times = {}
        
    async def track_model_load(self, model: str):
        """Track model loading time"""
        if model not in self.model_load_times:
            start_time = time.time()
            # Check if model is already loaded
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_base}/api/tags") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = data.get('models', [])
                        for m in models:
                            if m.get('name') == model:
                                # Model already loaded, estimate load time
                                load_time = time.time() - start_time
                                model_load_time.labels(
                                    model=model,
                                    container=self.container_name
                                ).set(load_time)
                                self.model_load_times[model] = load_time
                                break
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars per token average)"""
        return max(1, len(text) // 4)
    
    async def handle_generate(self, request: web.Request) -> web.Response:
        """Handle /api/generate endpoint with metrics tracking"""
        request_id = str(uuid.uuid4())
        
        try:
            # Parse request
            data = await request.json()
            model = data.get('model', 'unknown')
            prompt = data.get('prompt', '')
            stream = data.get('stream', True)
            
            # Update queue size
            self.pending_requests.append(request_id)
            queue_size.labels(
                model=model,
                container=self.container_name,
                endpoint='/api/generate'
            ).set(len(self.pending_requests))
            
            # Track model loading
            await self.track_model_load(model)
            
            # Start tracking
            self.tracker.start_request(request_id, model, self.container_name, '/api/generate')
            prompt_tokens = self.estimate_tokens(prompt)
            
            # Forward to Ollama
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_base}/api/generate",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    
                    if stream:
                        # Streaming response
                        response_tokens = 0
                        
                        async def generate():
                            nonlocal response_tokens
                            try:
                                async for line in resp.content:
                                    if line:
                                        # Parse streaming response
                                        try:
                                            chunk = json.loads(line)
                                            if 'response' in chunk:
                                                token_count = self.estimate_tokens(chunk['response'])
                                                response_tokens += token_count
                                                self.tracker.update_tokens(request_id, token_count)
                                        except json.JSONDecodeError:
                                            pass
                                        
                                        yield line
                                
                                # Complete tracking
                                self.tracker.end_request(request_id, prompt_tokens, response_tokens)
                                
                            except Exception as e:
                                self.tracker.end_request(request_id, 0, 0, error=str(type(e).__name__))
                                raise
                            finally:
                                # Update queue
                                if request_id in self.pending_requests:
                                    self.pending_requests.remove(request_id)
                                queue_size.labels(
                                    model=model,
                                    container=self.container_name,
                                    endpoint='/api/generate'
                                ).set(len(self.pending_requests))
                        
                        return web.Response(
                            body=generate(),
                            status=resp.status,
                            headers=resp.headers
                        )
                    
                    else:
                        # Non-streaming response
                        content = await resp.read()
                        
                        try:
                            data = json.loads(content)
                            response_text = data.get('response', '')
                            response_tokens = self.estimate_tokens(response_text)
                            
                            # Complete tracking
                            self.tracker.end_request(request_id, prompt_tokens, response_tokens)
                            
                        except json.JSONDecodeError:
                            self.tracker.end_request(request_id, 0, 0, error='json_decode_error')
                        
                        finally:
                            # Update queue
                            if request_id in self.pending_requests:
                                self.pending_requests.remove(request_id)
                            queue_size.labels(
                                model=model,
                                container=self.container_name,
                                endpoint='/api/generate'
                            ).set(len(self.pending_requests))
                        
                        return web.Response(
                            body=content,
                            status=resp.status,
                            headers=resp.headers
                        )
        
        except asyncio.TimeoutError:
            self.tracker.end_request(request_id, 0, 0, error='timeout')
            return web.Response(status=504, text='Inference timeout')
        
        except Exception as e:
            self.tracker.end_request(request_id, 0, 0, error=str(type(e).__name__))
            return web.Response(status=500, text=str(e))
    
    async def handle_chat(self, request: web.Request) -> web.Response:
        """Handle /api/chat endpoint with metrics tracking"""
        request_id = str(uuid.uuid4())
        
        try:
            # Parse request
            data = await request.json()
            model = data.get('model', 'unknown')
            messages = data.get('messages', [])
            stream = data.get('stream', True)
            
            # Calculate prompt tokens from all messages
            prompt_text = ' '.join([m.get('content', '') for m in messages])
            prompt_tokens = self.estimate_tokens(prompt_text)
            
            # Track request
            self.tracker.start_request(request_id, model, self.container_name, '/api/chat')
            
            # Forward to Ollama
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_base}/api/chat",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    
                    if stream:
                        # Handle streaming chat response
                        response_tokens = 0
                        
                        async def generate():
                            nonlocal response_tokens
                            try:
                                async for line in resp.content:
                                    if line:
                                        try:
                                            chunk = json.loads(line)
                                            if 'message' in chunk and 'content' in chunk['message']:
                                                token_count = self.estimate_tokens(chunk['message']['content'])
                                                response_tokens += token_count
                                                self.tracker.update_tokens(request_id, token_count)
                                        except json.JSONDecodeError:
                                            pass
                                        
                                        yield line
                                
                                self.tracker.end_request(request_id, prompt_tokens, response_tokens)
                                
                            except Exception as e:
                                self.tracker.end_request(request_id, 0, 0, error=str(type(e).__name__))
                                raise
                        
                        return web.Response(
                            body=generate(),
                            status=resp.status,
                            headers=resp.headers
                        )
                    
                    else:
                        # Non-streaming chat response
                        content = await resp.read()
                        
                        try:
                            data = json.loads(content)
                            message = data.get('message', {})
                            response_text = message.get('content', '')
                            response_tokens = self.estimate_tokens(response_text)
                            
                            self.tracker.end_request(request_id, prompt_tokens, response_tokens)
                            
                        except json.JSONDecodeError:
                            self.tracker.end_request(request_id, 0, 0, error='json_decode_error')
                        
                        return web.Response(
                            body=content,
                            status=resp.status,
                            headers=resp.headers
                        )
        
        except Exception as e:
            self.tracker.end_request(request_id, 0, 0, error=str(type(e).__name__))
            return web.Response(status=500, text=str(e))
    
    async def handle_passthrough(self, request: web.Request) -> web.Response:
        """Pass through other requests without tracking"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.ollama_base}{request.path_qs}"
            
            # Forward the request
            async with session.request(
                method=request.method,
                url=url,
                headers=request.headers,
                data=await request.read()
            ) as resp:
                body = await resp.read()
                return web.Response(
                    body=body,
                    status=resp.status,
                    headers=resp.headers
                )
    
    def create_app(self) -> web.Application:
        """Create the aiohttp application"""
        app = web.Application()
        
        # Route handlers
        app.router.add_post('/api/generate', self.handle_generate)
        app.router.add_post('/api/chat', self.handle_chat)
        
        # Pass through everything else
        app.router.add_route('*', '/{path:.*}', self.handle_passthrough)
        
        return app


def main():
    # Configuration
    ollama_host = os.environ.get('OLLAMA_HOST', 'localhost')
    ollama_port = int(os.environ.get('OLLAMA_PORT', '11434'))
    proxy_port = int(os.environ.get('PROXY_PORT', '11435'))
    metrics_port = int(os.environ.get('METRICS_PORT', '9202'))
    
    # Start metrics server
    start_http_server(metrics_port)
    print(f"Metrics server started on port {metrics_port}")
    
    # Create and start proxy
    wrapper = OllamaInferenceWrapper(ollama_host, ollama_port, metrics_port)
    app = wrapper.create_app()
    
    print(f"Ollama inference wrapper listening on port {proxy_port}")
    print(f"Forwarding to Ollama at {ollama_host}:{ollama_port}")
    
    web.run_app(app, host='0.0.0.0', port=proxy_port)


if __name__ == "__main__":
    main()