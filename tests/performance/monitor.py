"""
Real-time monitoring dashboard for performance tests.

Monitors API health and system metrics during load testing.
"""

import asyncio
import httpx
import psutil
import time
from datetime import datetime
import sys


class PerformanceMonitor:
    """Monitor system and API performance in real-time."""

    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.running = False
        self.metrics = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "total_time": 0.0,
            "last_check": None
        }

    def clear_screen(self):
        """Clear terminal screen."""
        print("\033[2J\033[H", end="")

    async def check_api_health(self):
        """Check if API is responsive."""
        try:
            async with httpx.AsyncClient() as client:
                start = time.time()
                response = await client.get(f"{self.api_url}/docs", timeout=5.0)
                elapsed = (time.time() - start) * 1000

                if response.status_code == 200:
                    self.metrics["requests"] += 1
                    self.metrics["successes"] += 1
                    self.metrics["total_time"] += elapsed
                    self.metrics["last_check"] = datetime.now()
                    return True, elapsed
                else:
                    self.metrics["requests"] += 1
                    self.metrics["failures"] += 1
                    return False, elapsed
        except Exception as e:
            self.metrics["requests"] += 1
            self.metrics["failures"] += 1
            return False, 0.0

    def get_system_metrics(self):
        """Get system resource usage."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Network stats
        net_io = psutil.net_io_counters()

        return {
            "cpu": cpu_percent,
            "memory": {
                "percent": memory.percent,
                "used_gb": memory.used / (1024**3),
                "total_gb": memory.total / (1024**3)
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": disk.used / (1024**3),
                "total_gb": disk.total / (1024**3)
            },
            "network": {
                "bytes_sent_mb": net_io.bytes_sent / (1024**2),
                "bytes_recv_mb": net_io.bytes_recv / (1024**2)
            }
        }

    def render_dashboard(self, api_healthy, api_response_time, sys_metrics):
        """Render the monitoring dashboard."""
        self.clear_screen()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print("=" * 80)
        print(" " * 20 + "AUTOGRADER PERFORMANCE MONITOR")
        print("=" * 80)
        print(f"Time: {now}                                    API: {self.api_url}")
        print()

        # API Health
        print("┌─ API HEALTH " + "─" * 65 + "┐")
        status_color = "\033[92m" if api_healthy else "\033[91m"  # Green or Red
        reset_color = "\033[0m"
        status_text = "HEALTHY" if api_healthy else "UNHEALTHY"

        print(f"│ Status:           {status_color}{status_text:12s}{reset_color}                                      │")
        print(f"│ Response Time:    {api_response_time:6.0f} ms                                              │")

        if self.metrics["requests"] > 0:
            success_rate = (self.metrics["successes"] / self.metrics["requests"]) * 100
            avg_time = self.metrics["total_time"] / self.metrics["successes"] if self.metrics["successes"] > 0 else 0

            print(f"│ Total Checks:     {self.metrics['requests']:6d}                                                 │")
            print(f"│ Success Rate:     {success_rate:5.1f}%                                                │")
            print(f"│ Avg Response:     {avg_time:6.0f} ms                                              │")

        if self.metrics["last_check"]:
            last_check_str = self.metrics["last_check"].strftime("%H:%M:%S")
            print(f"│ Last Check:       {last_check_str}                                                   │")

        print("└" + "─" * 78 + "┘")
        print()

        # System Resources
        print("┌─ SYSTEM RESOURCES " + "─" * 59 + "┐")

        # CPU
        cpu_bar = self.create_bar(sys_metrics["cpu"], 100, 30)
        cpu_color = self.get_color_for_percent(sys_metrics["cpu"])
        print(f"│ CPU Usage:    {cpu_color}{sys_metrics['cpu']:5.1f}%{reset_color} {cpu_bar}                              │")

        # Memory
        mem_percent = sys_metrics["memory"]["percent"]
        mem_bar = self.create_bar(mem_percent, 100, 30)
        mem_color = self.get_color_for_percent(mem_percent)
        mem_used = sys_metrics["memory"]["used_gb"]
        mem_total = sys_metrics["memory"]["total_gb"]
        print(f"│ Memory:       {mem_color}{mem_percent:5.1f}%{reset_color} {mem_bar} {mem_used:.1f}/{mem_total:.1f} GB    │")

        # Disk
        disk_percent = sys_metrics["disk"]["percent"]
        disk_bar = self.create_bar(disk_percent, 100, 30)
        disk_color = self.get_color_for_percent(disk_percent)
        disk_used = sys_metrics["disk"]["used_gb"]
        disk_total = sys_metrics["disk"]["total_gb"]
        print(f"│ Disk:         {disk_color}{disk_percent:5.1f}%{reset_color} {disk_bar} {disk_used:.0f}/{disk_total:.0f} GB   │")

        # Network
        net_sent = sys_metrics["network"]["bytes_sent_mb"]
        net_recv = sys_metrics["network"]["bytes_recv_mb"]
        print(f"│ Network:      ↑ {net_sent:7.1f} MB  ↓ {net_recv:7.1f} MB                                │")

        print("└" + "─" * 78 + "┘")
        print()

        # Instructions
        print("Press Ctrl+C to stop monitoring")

    def create_bar(self, value, max_value, width):
        """Create a text-based progress bar."""
        filled = int((value / max_value) * width)
        bar = "█" * filled + "░" * (width - filled)
        return bar

    def get_color_for_percent(self, percent):
        """Get color based on percentage."""
        if percent < 50:
            return "\033[92m"  # Green
        elif percent < 80:
            return "\033[93m"  # Yellow
        else:
            return "\033[91m"  # Red

    async def monitor_loop(self, interval=2):
        """Main monitoring loop."""
        self.running = True

        try:
            while self.running:
                # Check API health
                api_healthy, api_response_time = await self.check_api_health()

                # Get system metrics
                sys_metrics = self.get_system_metrics()

                # Render dashboard
                self.render_dashboard(api_healthy, api_response_time, sys_metrics)

                # Wait before next update
                await asyncio.sleep(interval)

        except KeyboardInterrupt:
            self.running = False
            print("\n\nMonitoring stopped")


async def main():
    """Run the monitor."""
    api_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

    print(f"Starting performance monitor for {api_url}...")
    print("Initializing...")
    await asyncio.sleep(1)

    monitor = PerformanceMonitor(api_url)
    await monitor.monitor_loop(interval=2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nMonitor stopped")

