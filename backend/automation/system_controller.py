import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

# ── Optional imports ──────────────────────────────────────────────
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    _PYCAW = True
except ImportError:
    _PYCAW = False

try:
    import screen_brightness_control as sbc
    _SBC = True
except ImportError:
    _SBC = False

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


class SystemController:
    """Controls OS-level hardware settings: volume, brightness, WiFi, etc."""

    # ── Volume ────────────────────────────────────────────────────
    def get_volume(self) -> dict:
        if not _PYCAW:
            return {"status": "error", "message": "pycaw not installed"}
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            current = volume.GetMasterVolumeLevelScalar()
            muted = volume.GetMute()
            return {"status": "ok", "volume": round(current * 100), "muted": bool(muted)}
        except Exception as e:
            logger.error(f"Error getting volume: {e}")
            return {"status": "error", "message": str(e)}

    def set_volume(self, level: int) -> dict:
        if not _PYCAW:
            return {"status": "error", "message": "pycaw not installed"}
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100)), None)
            return {"status": "ok", "volume": level}
        except Exception as e:
            logger.error(f"Error setting volume: {e}")
            return {"status": "error", "message": str(e)}

    def mute_volume(self) -> dict:
        if not _PYCAW:
            return {"status": "error", "message": "pycaw not installed"}
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(1, None)
            return {"status": "ok", "muted": True}
        except Exception as e:
            logger.error(f"Error muting: {e}")
            return {"status": "error", "message": str(e)}

    def unmute_volume(self) -> dict:
        if not _PYCAW:
            return {"status": "error", "message": "pycaw not installed"}
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(0, None)
            return {"status": "ok", "muted": False}
        except Exception as e:
            logger.error(f"Error unmuting: {e}")
            return {"status": "error", "message": str(e)}

    # ── Brightness ────────────────────────────────────────────────
    def get_brightness(self) -> dict:
        if not _SBC:
            return {"status": "error", "message": "screen-brightness-control not installed"}
        try:
            level = sbc.get_brightness()
            return {"status": "ok", "brightness": level[0] if isinstance(level, list) else level}
        except Exception as e:
            logger.error(f"Error getting brightness: {e}")
            return {"status": "error", "message": str(e)}

    def set_brightness(self, level: int) -> dict:
        if not _SBC:
            return {"status": "error", "message": "screen-brightness-control not installed"}
        try:
            sbc.set_brightness(max(0, min(100, level)))
            return {"status": "ok", "brightness": level}
        except Exception as e:
            logger.error(f"Error setting brightness: {e}")
            return {"status": "error", "message": str(e)}

    # ── WiFi ──────────────────────────────────────────────────────
    def get_wifi_status(self) -> dict:
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=5
            )
            connected = "State" in result.stdout and "connected" in result.stdout.lower()
            return {"status": "ok", "wifi_connected": connected, "details": result.stdout.strip()}
        except Exception as e:
            logger.error(f"Error checking WiFi: {e}")
            return {"status": "error", "message": str(e)}

    # ── Battery ───────────────────────────────────────────────────
    def get_battery(self) -> dict:
        if not _PSUTIL:
            return {"status": "error", "message": "psutil not installed"}
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return {"status": "ok", "message": "No battery detected (desktop PC)."}
            return {
                "status": "ok",
                "percent": battery.percent,
                "plugged_in": battery.power_plugged,
                "time_left_seconds": battery.secsleft
            }
        except Exception as e:
            logger.error(f"Error getting battery: {e}")
            return {"status": "error", "message": str(e)}

    # ── System Info ───────────────────────────────────────────────
    def get_system_info(self) -> dict:
        info = {
            "status": "ok",
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "node": platform.node()
        }
        
        # WiFi
        wifi_result = self.get_wifi_status()
        if wifi_result.get("status") == "ok":
            info["wifi_connected"] = wifi_result.get("wifi_connected", False)
            info["wifi_details"] = wifi_result.get("details", "")
        else:
            info["wifi_connected"] = False
            
        if _PSUTIL:
            info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            info["ram_total_gb"] = round(mem.total / (1024 ** 3), 2)
            info["ram_used_percent"] = mem.percent
            
            # Swap
            try:
                swap = psutil.swap_memory()
                info["swap_percent"] = swap.percent
            except Exception:
                info["swap_percent"] = 0
                
            # Temp (often fails on Windows without admin/third-party)
            try:
                temps = psutil.sensors_temperatures()
                if temps and list(temps.values())[0]:
                    info["temperature_c"] = list(temps.values())[0][0].current
                else:
                    info["temperature_c"] = None
            except Exception:
                info["temperature_c"] = None
        else:
            info["swap_percent"] = 0
            info["temperature_c"] = None
            
        return info

    # ── Process Listing ───────────────────────────────────────────
    def list_processes(self, top_n: int = 10) -> dict:
        if not _PSUTIL:
            return {"status": "error", "message": "psutil not installed"}
        try:
            procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                procs.append(proc.info)
            procs.sort(key=lambda p: p.get('cpu_percent', 0) or 0, reverse=True)
            return {"status": "ok", "processes": procs[:top_n]}
        except Exception as e:
            logger.error(f"Error listing processes: {e}")
            return {"status": "error", "message": str(e)}

    def kill_process(self, pid: int) -> dict:
        if not _PSUTIL:
            return {"status": "error", "message": "psutil not installed"}
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            return {"status": "ok", "message": f"Process {pid} ({proc.name()}) terminated."}
        except Exception as e:
            logger.error(f"Error killing process {pid}: {e}")
            return {"status": "error", "message": str(e)}
