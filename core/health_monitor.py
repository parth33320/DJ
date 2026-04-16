"""
Health Monitor - System monitoring and auto-recovery
Fixes: No health checks, no auto-restart, no alerts
"""

import threading
import time
import os
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Callable
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DEAD = "dead"


@dataclass
class HealthCheck:
    name: str
    check_func: Callable[[], bool]
    last_check: datetime = None
    last_status: HealthStatus = HealthStatus.HEALTHY
    consecutive_failures: int = 0
    recovery_func: Callable = None


class HealthMonitor:
    """
    System health monitoring with:
    - Component health checks
    - Auto-recovery
    - Resource monitoring
    - Alerting
    """
    
    def __init__(self, config):
        self.config = config
        self.checks: Dict[str, HealthCheck] = {}
        self.is_running = False
        self.monitor_thread = None
        
        # Thresholds
        self.cpu_warning = 80
        self.cpu_critical = 95
        self.memory_warning = 80
        self.memory_critical = 95
        self.disk_warning = 80
        self.disk_critical = 95
        
        # Alert callbacks
        self.alert_callbacks: List[Callable] = []
        
        # History
        self.history = []
        self.max_history = 1000
        
    def add_check(self, name: str, check_func: Callable, 
                  recovery_func: Callable = None):
        """Add a health check"""
        self.checks[name] = HealthCheck(
            name=name,
            check_func=check_func,
            recovery_func=recovery_func,
        )
    
    def add_alert_callback(self, callback: Callable):
        """Add callback for alerts"""
        self.alert_callbacks.append(callback)
    
    def start(self):
        """Start health monitoring"""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        print("💓 Health monitor started")
    
    def stop(self):
        """Stop health monitoring"""
        self.is_running = False
        print("💔 Health monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                status = self._run_all_checks()
                self._log_status(status)
                
                # Alert if critical
                if status['overall'] in [HealthStatus.CRITICAL, HealthStatus.DEAD]:
                    self._send_alert(status)
                
            except Exception as e:
                print(f"❌ Health monitor error: {e}")
            
            time.sleep(30)  # Check every 30 seconds
    
    def _run_all_checks(self) -> dict:
        """Run all health checks"""
        results = {}
        
        # System checks
        results['cpu'] = self._check_cpu()
        results['memory'] = self._check_memory()
        results['disk'] = self._check_disk()
        
        # Component checks
        for name, check in self.checks.items():
            try:
                is_healthy = check.check_func()
                check.last_check = datetime.now()
                
                if is_healthy:
                    check.last_status = HealthStatus.HEALTHY
                    check.consecutive_failures = 0
                else:
                    check.consecutive_failures += 1
                    
                    if check.consecutive_failures >= 3:
                        check.last_status = HealthStatus.CRITICAL
                        
                        # Try recovery
                        if check.recovery_func:
                            print(f"🔄 Attempting recovery for {name}")
                            try:
                                check.recovery_func()
                            except Exception as e:
                                print(f"❌ Recovery failed: {e}")
                    else:
                        check.last_status = HealthStatus.WARNING
                
                results[name] = check.last_status
                
            except Exception as e:
                check.last_status = HealthStatus.DEAD
                check.consecutive_failures += 1
                results[name] = HealthStatus.DEAD
                print(f"❌ Health check '{name}' error: {e}")
        
        # Overall status
        statuses = list(results.values())
        
        if HealthStatus.DEAD in statuses:
            results['overall'] = HealthStatus.DEAD
        elif HealthStatus.CRITICAL in statuses:
            results['overall'] = HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            results['overall'] = HealthStatus.WARNING
        else:
            results['overall'] = HealthStatus.HEALTHY
        
        return results
    
    def _check_cpu(self) -> HealthStatus:
        """Check CPU usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent >= self.cpu_critical:
                return HealthStatus.CRITICAL
            elif cpu_percent >= self.cpu_warning:
                return HealthStatus.WARNING
            return HealthStatus.HEALTHY
        except:
            return HealthStatus.WARNING
    
    def _check_memory(self) -> HealthStatus:
        """Check memory usage"""
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent >= self.memory_critical:
                return HealthStatus.CRITICAL
            elif memory.percent >= self.memory_warning:
                return HealthStatus.WARNING
            return HealthStatus.HEALTHY
        except:
            return HealthStatus.WARNING
    
    def _check_disk(self) -> HealthStatus:
        """Check disk usage"""
        try:
            disk = psutil.disk_usage('/')
            
            if disk.percent >= self.disk_critical:
                return HealthStatus.CRITICAL
            elif disk.percent >= self.disk_warning:
                return HealthStatus.WARNING
            return HealthStatus.HEALTHY
        except:
            return HealthStatus.WARNING
    
    def _log_status(self, status: dict):
        """Log status to history"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'status': {k: v.value if isinstance(v, HealthStatus) else v 
                       for k, v in status.items()},
        }
        
        self.history.append(entry)
        
        # Trim history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def _send_alert(self, status: dict):
        """Send alert for critical status"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'status': status['overall'].value,
            'details': {k: v.value if isinstance(v, HealthStatus) else v 
                        for k, v in status.items()},
        }
        
        print(f"🚨 HEALTH ALERT: {alert}")
        
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except:
                pass
    
    def get_status(self) -> dict:
        """Get current health status"""
        status = self._run_all_checks()
        
        # Add system info
        try:
            status['system'] = {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
            }
        except:
            pass
        
        return {
            k: v.value if isinstance(v, HealthStatus) else v 
            for k, v in status.items()
        }
    
    def get_history(self, hours: int = 24) -> List[dict]:
        """Get health history"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        return [
            entry for entry in self.history
            if datetime.fromisoformat(entry['timestamp']) > cutoff
        ]
