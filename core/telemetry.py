import psutil

def get_system_stats():
    return {
        "cpu_usage": psutil.cpu_percent(),
        "ram_usage": psutil.virtual_memory().percent,
        "gpu_temp": "Requer driver específico (ex: pynvml)"
    }