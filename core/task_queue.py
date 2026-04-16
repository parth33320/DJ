"""
Async Task Queue for background processing
Fixes: Blocking operations, no prioritization, no retry logic
"""

import threading
import queue
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Any, Optional
from datetime import datetime
import traceback


class TaskPriority(Enum):
    CRITICAL = 0   # Must run immediately (audio playback)
    HIGH = 1       # Run soon (next song download)
    NORMAL = 2     # Run when possible (analysis)
    LOW = 3        # Run when idle (self-improvement)
    BACKGROUND = 4 # Run overnight (training)


@dataclass(order=True)
class Task:
    priority: int
    created_at: float = field(compare=False)
    name: str = field(compare=False)
    func: Callable = field(compare=False)
    args: tuple = field(default=(), compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    retries: int = field(default=3, compare=False)
    retry_delay: float = field(default=1.0, compare=False)
    timeout: Optional[float] = field(default=None, compare=False)
    callback: Optional[Callable] = field(default=None, compare=False)
    error_callback: Optional[Callable] = field(default=None, compare=False)


class TaskQueue:
    """
    Priority-based async task queue with:
    - Priority levels
    - Retry logic
    - Timeout handling
    - Worker pool
    - Health monitoring
    """
    
    def __init__(self, num_workers=4):
        self.queue = queue.PriorityQueue()
        self.num_workers = num_workers
        self.workers = []
        self.is_running = False
        
        # Stats
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.tasks_pending = 0
        
        # Health
        self.last_activity = datetime.now()
        self.worker_status = {}
        
    def start(self):
        """Start worker threads"""
        if self.is_running:
            return
            
        self.is_running = True
        
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=True,
                name=f"TaskWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)
            self.worker_status[i] = 'idle'
        
        print(f"✅ Task queue started with {self.num_workers} workers")
    
    def stop(self):
        """Stop all workers"""
        self.is_running = False
        
        # Add poison pills to stop workers
        for _ in range(self.num_workers):
            self.queue.put(Task(
                priority=999,
                created_at=time.time(),
                name='__STOP__',
                func=lambda: None
            ))
        
        # Wait for workers
        for worker in self.workers:
            worker.join(timeout=2)
        
        self.workers.clear()
        print("🛑 Task queue stopped")
    
    def add(self, 
            func: Callable,
            args: tuple = (),
            kwargs: dict = None,
            priority: TaskPriority = TaskPriority.NORMAL,
            name: str = None,
            retries: int = 3,
            timeout: float = None,
            callback: Callable = None,
            error_callback: Callable = None) -> None:
        """Add task to queue"""
        
        task = Task(
            priority=priority.value,
            created_at=time.time(),
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs or {},
            retries=retries,
            timeout=timeout,
            callback=callback,
            error_callback=error_callback,
        )
        
        self.queue.put(task)
        self.tasks_pending += 1
    
    def add_critical(self, func, *args, **kwargs):
        """Shortcut for critical priority tasks"""
        self.add(func, args, kwargs, priority=TaskPriority.CRITICAL)
    
    def add_high(self, func, *args, **kwargs):
        """Shortcut for high priority tasks"""
        self.add(func, args, kwargs, priority=TaskPriority.HIGH)
    
    def add_low(self, func, *args, **kwargs):
        """Shortcut for low priority tasks"""
        self.add(func, args, kwargs, priority=TaskPriority.LOW)
    
    def _worker_loop(self, worker_id):
        """Main worker loop"""
        while self.is_running:
            try:
                # Get task (blocks until available)
                task = self.queue.get(timeout=1)
                
                if task.name == '__STOP__':
                    break
                
                self.worker_status[worker_id] = f'running:{task.name}'
                self.last_activity = datetime.now()
                
                # Execute task with retries
                success = self._execute_task(task, worker_id)
                
                if success:
                    self.tasks_completed += 1
                else:
                    self.tasks_failed += 1
                
                self.tasks_pending -= 1
                self.worker_status[worker_id] = 'idle'
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Worker {worker_id} error: {e}")
                self.worker_status[worker_id] = 'error'
    
    def _execute_task(self, task: Task, worker_id: int) -> bool:
        """Execute task with retry logic"""
        last_error = None
        
        for attempt in range(task.retries):
            try:
                # Execute with timeout if specified
                if task.timeout:
                    result = self._run_with_timeout(
                        task.func, 
                        task.args, 
                        task.kwargs,
                        task.timeout
                    )
                else:
                    result = task.func(*task.args, **task.kwargs)
                
                # Success callback
                if task.callback:
                    try:
                        task.callback(result)
                    except:
                        pass
                
                return True
                
            except Exception as e:
                last_error = e
                print(f"⚠️ Task '{task.name}' attempt {attempt + 1}/{task.retries} failed: {e}")
                
                if attempt < task.retries - 1:
                    time.sleep(task.retry_delay * (attempt + 1))
        
        # All retries failed
        print(f"❌ Task '{task.name}' failed after {task.retries} attempts")
        
        if task.error_callback:
            try:
                task.error_callback(last_error)
            except:
                pass
        
        return False
    
    def _run_with_timeout(self, func, args, kwargs, timeout):
        """Run function with timeout"""
        result = [None]
        error = [None]
        
        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                error[0] = e
        
        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            raise TimeoutError(f"Task timed out after {timeout}s")
        
        if error[0]:
            raise error[0]
        
        return result[0]
    
    def get_stats(self):
        """Get queue statistics"""
        return {
            'pending': self.tasks_pending,
            'completed': self.tasks_completed,
            'failed': self.tasks_failed,
            'workers': self.worker_status.copy(),
            'last_activity': self.last_activity.isoformat(),
            'queue_size': self.queue.qsize(),
        }
    
    def is_healthy(self) -> bool:
        """Check if queue is healthy"""
        # Check for stuck workers
        if (datetime.now() - self.last_activity).seconds > 300:
            return False
        
        # Check for error workers
        if 'error' in self.worker_status.values():
            return False
        
        return True
