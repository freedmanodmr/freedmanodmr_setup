# -*- coding: utf-8 -*-
"""
Created on Thu Dec 11 13:45:03 2025

@author: ChatGPT + a little bit of ODMR_user
"""

# -*- coding: utf-8 -*-
"""
Pyro5 server for TimeTagger20 — expanded driver

Wraps a large portion of the TimeTagger Python API with safe fallbacks so this
class can be used remotely via Pyro5. Methods return plain Python types
(lists, dicts, ints, floats) where possible for easy RPC transport.
"""

import time
import numpy as np
from Pyro5.api import expose, Daemon, serve
import TimeTagger

@expose
class TimeTagger20():
    """
    Pyro5-wrapped TimeTagger20 driver.
    All methods call the underlying TimeTagger instance where available.
    """

    def __init__(self, uri=None, start_immediately=False, create_virtual=True):
        # createTimeTagger or createTimeTaggerVirtual depending on request
        if create_virtual and hasattr(TimeTagger, "createTimeTaggerVirtual"):
            self.tagger = TimeTagger.createTimeTaggerVirtual()
        else:
            self.tagger = TimeTagger.createTimeTagger()
        self._running = False
        if start_immediately:
            try:
                self.tagger.start()
                self._running = True
            except Exception:
                # some TimeTagger types may not require explicit start
                pass

        # Keep references to created virtual objects so we can clean them up
        self._virtual_objects = {}

    # ----------------------
    # Basic control
    # ----------------------
    def start(self):
        """Start measurements if supported."""
        if hasattr(self.tagger, "start"):
            self.tagger.start()
            self._running = True
            return True
        return False

    def stop(self):
        """Stop measurements if supported."""
        if hasattr(self.tagger, "stop"):
            self.tagger.stop()
            self._running = False
            return True
        return False

    def startFor(self, seconds: float):
        """
        Start measurements for a given time (seconds) if supported by API.
        Returns True if this call was invoked.
        """
        if hasattr(self.tagger, "startFor"):
            self.tagger.startFor(float(seconds))
            self._running = True
            return True
        # fallback: start + time.sleep + stop (blocking)
        self.start()
        time.sleep(float(seconds))
        self.stop()
        return True

    def close(self):
        """Stop and release tagger object."""
        try:
            self.stop()
        except Exception:
            pass
        try:
            # freeTimeTagger is available in API
            if hasattr(TimeTagger, "freeTimeTagger"):
                TimeTagger.freeTimeTagger(self.tagger)
        except Exception:
            pass
        self.tagger = None
        return True

    # ----------------------
    # Countrate / Counter helpers
    # ----------------------
    def create_counter(self, channels, binwidth_ns=1_000_000, n_values=1):
        """
        Create and register a Counter object and return an id key.
        channels: list or single int
        binwidth_ns: width in ns for countrate bins (int)
        n_values: number of values to retrieve
        """
        if isinstance(channels, int):
            channels = [channels]
        counter = TimeTagger.Counter(self.tagger, channels=channels,
                                     binwidth=int(binwidth_ns), n_values=int(n_values))
        key = f"counter_{id(counter)}"
        self._virtual_objects[key] = counter
        return key

    def counter_get_data(self, counter_key):
        """Return Counter::getData() as a dict {channel: [values...]}"""
        counter = self._virtual_objects.get(counter_key)
        if counter is None:
            raise KeyError("counter not found")
        data = counter.getData()
        # Convert to plain Python types
        return {int(k): list(v) for k, v in data.items()}

    def counter_get_index(self, counter_key):
        """Return Counter::getIndex() if available."""
        counter = self._virtual_objects.get(counter_key)
        if counter is None:
            raise KeyError("counter not found")
        if hasattr(counter, "getIndex"):
            return counter.getIndex()
        else:
            return None

    # ----------------------
    # Simple count rate convenience
    # ----------------------
    def count_rate(self, channel, integration_time_ms=100):
        """
        Convenience countrate: create a Counter, wait, read rate and delete it.
        Returns rate in counts / second.
        """
        binwidth_ns = int(integration_time_ms * 1e6)
        key = self.create_counter(int(channel), binwidth_ns=binwidth_ns, n_values=1)
        # wait for data to accumulate
        time.sleep(integration_time_ms / 1000.0 + 0.01)
        data = self.counter_get_data(key)
        # cleanup
        self._virtual_objects.pop(key, None)
        vals = data.get(int(channel), [0])
        rate = vals[0] / (integration_time_ms / 1000.0)
        return float(rate)

    # ----------------------
    # Measurements: Histogram, Correlation, StartStop, etc.
    # ----------------------
    def histogram(self, photon_channel, trig_channel,
                  binwidth_ns=4, n_bins=1000, n_cycles=None,
                  trig_edge="rising"):
        """
        Create a Histogram measurement and return data.
        trig_edge: "rising" or "falling"
        """

        # Select edge
        if trig_edge.lower() == "falling":
            trig = TimeTagger.FallingEdge(int(trig_channel))
        else:
            trig = TimeTagger.RisingEdge(int(trig_channel))

        hist = TimeTagger.Histogram(
            self.tagger,
            int(photon_channel),
            trig,
            int(binwidth_ns),
            int(n_bins)
        )

        key = f"hist_{id(hist)}"
        self._virtual_objects[key] = hist

        if n_cycles is not None:
            approx_seconds = (n_cycles * binwidth_ns * n_bins) / 1e9
            approx_seconds = min(approx_seconds, 30.0)
            time.sleep(approx_seconds)

        return np.array(hist.getData()).tolist()

    def histogram_logbins(self, photon_channel, trig_channel,
                          start_ns, stop_ns, n_bins,
                          trig_edge="rising"):
        """
        HistogramLogBins with trigger edge selection.
        """

        if not hasattr(TimeTagger, "HistogramLogBins"):
            raise NotImplementedError("HistogramLogBins not available")

        # Select edge
        if trig_edge.lower() == "falling":
            trig = TimeTagger.FallingEdge(int(trig_channel))
        else:
            trig = TimeTagger.RisingEdge(int(trig_channel))

        h = TimeTagger.HistogramLogBins(
            self.tagger,
            int(photon_channel),
            trig,
            float(start_ns),
            float(stop_ns),
            int(n_bins)
        )

        return np.array(h.getData()).tolist()

    def histogram2d(self, ch_x, ch_y, binwidth_ns=4, n_bins_x=100, n_bins_y=100):
        """
        Create a 2D histogram if supported and return data as nested lists.
        """
        if hasattr(TimeTagger, "Histogram2D"):
            h2 = TimeTagger.Histogram2D(self.tagger, int(ch_x), int(ch_y),
                                       int(binwidth_ns), int(n_bins_x), int(n_bins_y))
            # getData might return a 2D array-like
            data = np.array(h2.getData())
            return data.tolist()
        else:
            raise NotImplementedError("Histogram2D not available")

    def correlation(self, chA, chB, binwidth_ns=1, n_bins=1000, n_cycles=None):
        """
        Create Correlation measurement and return data as list.
        """
        corr = TimeTagger.Correlation(self.tagger, int(chA), int(chB), int(binwidth_ns), int(n_bins))
        key = f"corr_{id(corr)}"
        self._virtual_objects[key] = corr
        if n_cycles is not None:
            # approximate wait, clamp small
            time.sleep(min(n_cycles * binwidth_ns / 1e9, 10.0))
        try:
            return np.array(corr.getData()).tolist()
        except Exception:
            return []

    # ----------------------
    # Virtual channels constructors
    # ----------------------
    def create_delayed_channel(self, input_channel, delay_ns):
        """
        Create a DelayedChannel (virtual) and return its virtual channel id.
        """
        if not hasattr(TimeTagger, "DelayedChannel"):
            raise NotImplementedError("DelayedChannel not available")
        obj = TimeTagger.DelayedChannel(self.tagger, int(input_channel), float(delay_ns))
        key = f"delayed_{id(obj)}"
        self._virtual_objects[key] = obj
        # return the virtual channel number (getChannel() or getChannels())
        try:
            ch = obj.getChannel()
            return {"key": key, "virtual_channel": int(ch)}
        except Exception:
            return {"key": key, "virtual_channel": None}

    def create_gated_channel(self, input_channel, gate_start_channel, gate_stop_channel,
                             initial_closed=True):
        """
        Create a GatedChannel and return its id and virtual channel number if available.
        """
        if not hasattr(TimeTagger, "GatedChannel"):
            raise NotImplementedError("GatedChannel not available")
        initial = TimeTagger.GatedChannelInitial_Closed if initial_closed else TimeTagger.GatedChannelInitial_Open
        gate = TimeTagger.GatedChannel(self.tagger, int(input_channel),
                                       int(gate_start_channel), int(gate_stop_channel),
                                       initial=initial)
        key = f"gated_{id(gate)}"
        self._virtual_objects[key] = gate
        try:
            return {"key": key, "virtual_channel": int(gate.getChannel())}
        except Exception:
            return {"key": key, "virtual_channel": None}

    def create_coincidence(self, channels, window_ns):
        """
        Create a Coincidence virtual channel combining 'channels' within 'window_ns'.
        Returns a dict with key and virtual channel id if available.
        """
        if not hasattr(TimeTagger, "Coincidence"):
            raise NotImplementedError("Coincidence not available")
        if isinstance(channels, int):
            channels = [channels]
        # API: Coincidence(tagger, channelsVec, window)
        obj = TimeTagger.Coincidence(self.tagger, channels, float(window_ns))
        key = f"coinc_{id(obj)}"
        self._virtual_objects[key] = obj
        try:
            return {"key": key, "virtual_channel": int(obj.getChannel())}
        except Exception:
            return {"key": key, "virtual_channel": None}

    def delete_virtual(self, key):
        """Delete a previously created virtual object by key."""
        obj = self._virtual_objects.pop(key, None)
        # let Python GC take care; explicit cleanup if available
        if obj is None:
            return False
        if hasattr(obj, "close"):
            try:
                obj.close()
            except Exception:
                pass
        return True

    # ----------------------
    # Logger and reference clock
    # ----------------------
    def set_logger(self, level="INFO"):
        """Set the TimeTagger library logger if supported."""
        if hasattr(TimeTagger, "setLogger"):
            TimeTagger.setLogger(level)
            return True
        return False

    def set_reference_clock(self, source_name: str):
        """Map to TimeTaggerSource::setReferenceClock or similar API if present."""
        if hasattr(TimeTagger, "TimeTaggerSource") and hasattr(TimeTagger.TimeTaggerSource, "setReferenceClock"):
            TimeTagger.TimeTaggerSource.setReferenceClock(source_name)
            return True
        # Fallback: try tagger method
        if hasattr(self.tagger, "setReferenceClock"):
            self.tagger.setReferenceClock(source_name)
            return True
        raise NotImplementedError("setReferenceClock not available on this installation")

    # ----------------------
    # Hardware information & control
    # ----------------------
    @staticmethod
    def scan_taggger_devices():
        """Wrapper for TimeTagger.scanTimeTagger() => returns list of device descriptors."""
        if hasattr(TimeTagger, "scanTimeTagger"):
            devices = TimeTagger.scanTimeTagger()
            # convert to plain Python structures if possible
            try:
                return list(devices)
            except Exception:
                return devices
        return []

    def get_serial(self):
        """Return the serial of the connected tagger if supported."""
        if hasattr(self.tagger, "getSerial"):
            return str(self.tagger.getSerial())
        return None

    def get_model(self):
        if hasattr(self.tagger, "getModel"):
            return str(self.tagger.getModel())
        return None

    def get_sensor_data(self):
        if hasattr(self.tagger, "getSensorData"):
            return dict(self.tagger.getSensorData())
        return {}

    def get_configuration(self):
        if hasattr(self.tagger, "getConfiguration"):
            return dict(self.tagger.getConfiguration())
        return {}

    def set_trigger_level(self, channel, level_volts):
        """Set trigger level for a physical input if API supports it."""
        if hasattr(self.tagger, "setTriggerLevel"):
            self.tagger.setTriggerLevel(int(channel), float(level_volts))
            return True
        return False

    def get_trigger_level_range(self, channel):
        """Get allowed trigger level range for a channel."""
        if hasattr(self.tagger, "getTriggerLevelRange"):
            low, high = self.tagger.getTriggerLevelRange(int(channel))
            return {"min": float(low), "max": float(high)}
        return None

    def set_input_delay(self, channel, delay_ns):
        """Set input delay for a physical channel."""
        if hasattr(self.tagger, "setInputDelay"):
            self.tagger.setInputDelay(int(channel), float(delay_ns))
            return True
        return False

    def get_overflows(self):
        """Return getOverflows() if present."""
        if hasattr(self.tagger, "getOverflows"):
            return int(self.tagger.getOverflows())
        return 0

    def set_test_signal_divider(self, divider):
        """Set test signal divider if supported."""
        if hasattr(self.tagger, "setTestSignalDivider"):
            self.tagger.setTestSignalDivider(int(divider))
            return True
        return False

    def set_conditional_filter(self, channel, config):
        """
        Set conditional filter for a channel if supported.
        'config' should be a dict or object according to the underlying API.
        """
        if hasattr(self.tagger, "setConditionalFilter"):
            return self.tagger.setConditionalFilter(int(channel), config)
        raise NotImplementedError("Conditional filter not supported in this build")

    # ----------------------
    # Streaming / FileWriter / FileReader
    # ----------------------
    def create_file_writer(self, filename, overwrite=True):
        """
        Create a FileWriter that dumps tags to disk. Returns a key.
        """
        if not hasattr(TimeTagger, "FileWriter"):
            raise NotImplementedError("FileWriter not available")
        fw = TimeTagger.FileWriter(self.tagger, filename, overwrite)
        key = f"filewriter_{id(fw)}"
        self._virtual_objects[key] = fw
        return key

    def close_file_writer(self, key):
        fw = self._virtual_objects.get(key)
        if fw is None:
            return False
        if hasattr(fw, "close"):
            fw.close()
        self._virtual_objects.pop(key, None)
        return True

    def file_reader_read(self, filename, max_events=None):
        """
        Read a time-tag stream file with FileReader and return a small summary.
        """
        if not hasattr(TimeTagger, "FileReader"):
            raise NotImplementedError("FileReader not available")
        fr = TimeTagger.FileReader(filename)
        # iterate small number of tags to create a summary
        count = 0
        first_ts = None
        last_ts = None
        for t in fr:
            if first_ts is None:
                first_ts = t
            last_ts = t
            count += 1
            if max_events is not None and count >= max_events:
                break
        try:
            fr.close()
        except Exception:
            pass
        return {"events_read": count, "first": first_ts, "last": last_ts}

    def create_timetag_stream(self, buffer_size=100000):
        """
        Create a TimeTagStream object for streaming raw tags if available.
        Returns a key for the created stream object.
        """
        if not hasattr(TimeTagger, "TimeTagStream"):
            raise NotImplementedError("TimeTagStream not available")
        stream = TimeTagger.TimeTagStream(self.tagger, int(buffer_size))
        key = f"stream_{id(stream)}"
        self._virtual_objects[key] = stream
        return key

    def stream_get_next(self, stream_key, max_items=1000):
        """
        Read next chunk of events from a streaming object.
        Returns Python list of tags / timestamps depending on implementation.
        """
        stream = self._virtual_objects.get(stream_key)
        if stream is None:
            raise KeyError("stream not found")
        # API details vary: try to call getData / read / pop
        if hasattr(stream, "getData"):
            data = stream.getData(int(max_items))
            # convert to list
            try:
                return list(data)
            except Exception:
                return data
        if hasattr(stream, "read"):
            data = stream.read(int(max_items))
            return list(data)
        raise NotImplementedError("stream object does not support getData/read")

    # ----------------------
    # Custom measurement (low-level)
    # ----------------------
    def create_custom_measurement(self, classname, *args, **kwargs):
        """
        Create an arbitrary measurement object by name if available in TimeTagger module.
        Returns a key for the created object or raises if not found.
        Example: create_custom_measurement('CustomMeasurement', params...)
        """
        if not hasattr(TimeTagger, classname):
            raise AttributeError(f"{classname} not available in TimeTagger module")
        cls = getattr(TimeTagger, classname)
        obj = cls(self.tagger, *args, **kwargs)
        key = f"{classname}_{id(obj)}"
        self._virtual_objects[key] = obj
        return key

    def custom_get_data(self, key):
        """
        Generic getData wrapper for custom objects stored in _virtual_objects.
        Returns Python-friendly data where possible.
        """
        obj = self._virtual_objects.get(key)
        if obj is None:
            raise KeyError("object not found")
        if hasattr(obj, "getData"):
            return obj.getData()
        raise NotImplementedError("object has no getData method")

    # ----------------------
    # Snapshot & utility
    # ----------------------
    def snapshot(self):
        """
        Return a snapshot dict for GUI / Nspyre integration.
        Keep returns minimal and JSON-friendly.
        """
        result = {
            "running": self._running,
            "virtual_objects": list(self._virtual_objects.keys())
        }
        # hardware info best-effort
        try:
            result.update({
                "model": self.get_model(),
                "serial": self.get_serial(),
            })
        except Exception:
            pass
        return result

    def list_channels(self):
        """
        Return the list of available physical channels.
        """
        if hasattr(self.tagger, "getChannelList"):
            ch_vector = self.tagger.getChannelList()
            try:
                return [int(ch) for ch in ch_vector]
            except Exception:
                return list(ch_vector)
        return []

# ----------------------
# Start the Pyro5 server
# ----------------------
#if __name__ == "__main__":
#    daemon = Daemon()  # Pyro daemon
#    uri = daemon.register(TimeTagger20)
#    print("TimeTagger20 ready. URI =", uri)
#    daemon.requestLoop()

