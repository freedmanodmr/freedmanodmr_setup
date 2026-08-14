# -*- coding: utf-8 -*-
"""
Created on Thu Jul 16 21:12:00 2026

@author: ODMR_user
"""

# -*- coding: utf-8 -*-
"""
Thorlabs PM100D driver for nspyre InstrumentServer.

Uses:
    C:\\Program Files\\IVI Foundation\\VISA\\Win64\\Bin\\TLPM_64.dll

Main methods:
    get_power()                         -> power in watts
    average_power(integration_time_s)   -> mean power in watts
    set_wavelength(wavelength_nm)
    get_wavelength()
    close()
"""

import math
import time
from ctypes import (
    POINTER,
    byref,
    c_bool,
    c_char_p,
    c_double,
    c_int,
    c_uint32,
    c_ulong,
    create_string_buffer,
    cdll,
)
from pathlib import Path


class PM100DError(RuntimeError):
    """Raised when the Thorlabs PM100D DLL returns an error."""


class PM100D:
    """Driver for a Thorlabs PM100D optical power meter."""

    DEFAULT_DLL_PATH = (
        r"C:\Program Files\IVI Foundation\VISA\Win64\Bin\TLPM_64.dll"
    )

    POWER_UNIT_WATTS = 0
    POWER_UNIT_DBM = 1

    def __init__(
        self,
        dll_path: str = DEFAULT_DLL_PATH,
        resource_index: int = 0,
        resource_name: str | None = None,
        id_query: bool = True,
        reset_device: bool = False,
        timeout_s: float = 5.0,
    ):
        """
        Connect to a PM100D.

        Args:
            dll_path:
                Full path to TLPM_64.dll.
            resource_index:
                Index of the detected PM100D to use when resource_name is None.
            resource_name:
                Optional explicit VISA-style resource string. Automatic discovery
                is used when this is None.
            id_query:
                Ask the DLL to verify instrument identity during initialization.
            reset_device:
                Reset the PM100D during initialization.
            timeout_s:
                Maximum time allowed for automatic discovery.
        """
        self.dll_path = str(dll_path)
        self.resource_index = int(resource_index)
        self.resource_name = resource_name
        self.timeout_s = float(timeout_s)

        self._lib = None
        self._session = c_ulong(0)
        self._connected = False
        self._last_wavelength_nm = None

        self._load_library()
        self._configure_ctypes_signatures()

        if self.resource_name is None:
            self.resource_name = self._discover_resource()

        self._connect(
            id_query=bool(id_query),
            reset_device=bool(reset_device),
        )

        # Use watts for all returned measurements.
        self.set_power_unit_watts()

    # ------------------------------------------------------------------
    # DLL setup
    # ------------------------------------------------------------------

    def _load_library(self):
        path = Path(self.dll_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Could not find the Thorlabs DLL:\n{path}"
            )

        try:
            self._lib = cdll.LoadLibrary(str(path))
        except OSError as exc:
            raise PM100DError(
                f"Could not load TLPM DLL from {path}: {exc}"
            ) from exc

    def _configure_ctypes_signatures(self):
        """
        Define the argument and return types used by this driver.

        Explicit signatures are important on 64-bit Python because they prevent
        ctypes from guessing pointer and integer sizes incorrectly.
        """
        lib = self._lib

        lib.TLPM_findRsrc.argtypes = [
            c_ulong,
            POINTER(c_uint32),
        ]
        lib.TLPM_findRsrc.restype = c_int

        lib.TLPM_getRsrcName.argtypes = [
            c_ulong,
            c_uint32,
            c_char_p,
        ]
        lib.TLPM_getRsrcName.restype = c_int

        lib.TLPM_init.argtypes = [
            c_char_p,
            c_bool,
            c_bool,
            POINTER(c_ulong),
        ]
        lib.TLPM_init.restype = c_int

        lib.TLPM_close.argtypes = [c_ulong]
        lib.TLPM_close.restype = c_int

        lib.TLPM_errorMessage.argtypes = [
            c_ulong,
            c_int,
            c_char_p,
        ]
        lib.TLPM_errorMessage.restype = c_int

        lib.TLPM_setWavelength.argtypes = [
            c_ulong,
            c_double,
        ]
        lib.TLPM_setWavelength.restype = c_int

        lib.TLPM_getWavelength.argtypes = [
            c_ulong,
            c_int,
            POINTER(c_double),
        ]
        lib.TLPM_getWavelength.restype = c_int

        lib.TLPM_setPowerUnit.argtypes = [
            c_ulong,
            c_int,
        ]
        lib.TLPM_setPowerUnit.restype = c_int

        lib.TLPM_measPower.argtypes = [
            c_ulong,
            POINTER(c_double),
        ]
        lib.TLPM_measPower.restype = c_int

        # These functions may be useful but are not required by every scan.
        if hasattr(lib, "TLPM_setAvgCnt"):
            lib.TLPM_setAvgCnt.argtypes = [
                c_ulong,
                c_int,
            ]
            lib.TLPM_setAvgCnt.restype = c_int

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _error_text(self, error_code: int) -> str:
        message = create_string_buffer(512)

        try:
            self._lib.TLPM_errorMessage(
                self._session,
                int(error_code),
                message,
            )
            decoded = message.value.decode(
                "utf-8",
                errors="replace",
            )
            return decoded or f"Unknown TLPM error {error_code}"
        except Exception:
            return f"TLPM error {error_code}"

    def _check(self, result: int, operation: str):
        """
        Check a TLPM return code.

        Thorlabs/IVI functions normally return zero for success, negative values
        for errors, and may use positive values for warnings.
        """
        result = int(result)

        if result < 0:
            raise PM100DError(
                f"{operation} failed: {self._error_text(result)} "
                f"(code {result})"
            )

        return result

    def _require_connection(self):
        if not self._connected or self._session.value == 0:
            raise PM100DError("PM100D is not connected.")

    # ------------------------------------------------------------------
    # Discovery and connection
    # ------------------------------------------------------------------

    def _discover_resource(self) -> str:
        deadline = time.monotonic() + self.timeout_s
        last_count = 0

        while time.monotonic() < deadline:
            count = c_uint32(0)

            result = self._lib.TLPM_findRsrc(
                c_ulong(0),
                byref(count),
            )
            self._check(result, "PM100D resource discovery")

            last_count = count.value

            if count.value > self.resource_index:
                name = create_string_buffer(1024)

                result = self._lib.TLPM_getRsrcName(
                    c_ulong(0),
                    c_uint32(self.resource_index),
                    name,
                )
                self._check(result, "Reading PM100D resource name")

                resource = name.value.decode(
                    "ascii",
                    errors="replace",
                )

                if not resource:
                    raise PM100DError(
                        "The PM100D was found, but its resource name was empty."
                    )

                return resource

            time.sleep(0.1)

        raise PM100DError(
            "No PM100D was detected. "
            f"Detected resource count: {last_count}. "
            "Close the Thorlabs OPM GUI and check the USB connection."
        )

    def _connect(
        self,
        id_query: bool,
        reset_device: bool,
    ):
        resource_bytes = self.resource_name.encode("ascii")

        result = self._lib.TLPM_init(
            resource_bytes,
            c_bool(id_query),
            c_bool(reset_device),
            byref(self._session),
        )
        self._check(result, "Connecting to PM100D")

        if self._session.value == 0:
            raise PM100DError(
                "TLPM_init returned successfully but produced an invalid session."
            )

        self._connected = True

    @property
    def connected(self) -> bool:
        return self._connected

    def get_resource_name(self) -> str:
        return self.resource_name

    # ------------------------------------------------------------------
    # Wavelength configuration
    # ------------------------------------------------------------------

    def set_wavelength(
        self,
        wavelength_nm: float,
        round_to_integer: bool = True,
    ) -> float:
        """
        Set the PM100D wavelength correction.

        Args:
            wavelength_nm:
                Requested wavelength in nanometers.
            round_to_integer:
                Round to the nearest integer before sending.

        Returns:
            The wavelength value sent to the PM100D.
        """
        self._require_connection()

        wavelength_nm = float(wavelength_nm)

        if not math.isfinite(wavelength_nm):
            raise ValueError("Wavelength must be finite.")

        if round_to_integer:
            # Python's round() uses banker's rounding for exact .5 values.
            # This gives conventional nearest-integer rounding for positive nm.
            wavelength_nm = float(math.floor(wavelength_nm + 0.5))

        # Avoid unnecessary USB commands.
        if wavelength_nm == self._last_wavelength_nm:
            return wavelength_nm

        result = self._lib.TLPM_setWavelength(
            self._session,
            c_double(wavelength_nm),
        )
        self._check(result, "Setting PM100D wavelength")

        self._last_wavelength_nm = wavelength_nm
        return wavelength_nm

    def get_wavelength(self) -> float:
        """
        Return the currently configured wavelength in nanometers.

        Attribute selector 0 requests the current value in the TLPM API.
        """
        self._require_connection()

        wavelength_nm = c_double()

        result = self._lib.TLPM_getWavelength(
            self._session,
            c_int(0),
            byref(wavelength_nm),
        )
        self._check(result, "Reading PM100D wavelength")

        self._last_wavelength_nm = float(wavelength_nm.value)
        return float(wavelength_nm.value)

    # ------------------------------------------------------------------
    # Power acquisition
    # ------------------------------------------------------------------

    def set_power_unit_watts(self):
        """Configure the PM100D to return power in watts."""
        self._require_connection()

        result = self._lib.TLPM_setPowerUnit(
            self._session,
            c_int(self.POWER_UNIT_WATTS),
        )
        self._check(result, "Setting PM100D power unit to watts")

    def set_hardware_average_count(self, count: int):
        """
        Set the PM100D's internal averaging count when supported by the DLL.

        Python-side time averaging in average_power() is usually preferable for
        synchronizing the PM100D with your lock-in integration.
        """
        self._require_connection()

        if not hasattr(self._lib, "TLPM_setAvgCnt"):
            raise PM100DError(
                "This installed TLPM DLL does not expose TLPM_setAvgCnt."
            )

        count = int(count)

        if count < 1:
            raise ValueError("Average count must be at least 1.")

        result = self._lib.TLPM_setAvgCnt(
            self._session,
            c_int(count),
        )
        self._check(result, "Setting PM100D average count")

    def get_power(self) -> float:
        """Read one optical-power measurement in watts."""
        self._require_connection()

        power_w = c_double()

        result = self._lib.TLPM_measPower(
            self._session,
            byref(power_w),
        )
        self._check(result, "Reading PM100D power")

        value = float(power_w.value)

        if not math.isfinite(value):
            raise PM100DError(
                f"PM100D returned a non-finite power value: {value}"
            )

        return value

    # Compatibility alias.
    read_power = get_power

    def average_power(
        self,
        integration_time_s: float,
        sample_interval_s: float = 0.005,
        ignore_invalid: bool = True,
    ) -> float:
        """
        Average power over a specified duration.

        Args:
            integration_time_s:
                Total acquisition duration in seconds.
            sample_interval_s:
                Delay between read attempts.
            ignore_invalid:
                Skip non-finite or failed samples when True.

        Returns:
            Mean optical power in watts.
        """
        self._require_connection()

        integration_time_s = float(integration_time_s)
        sample_interval_s = float(sample_interval_s)

        if integration_time_s <= 0:
            raise ValueError("integration_time_s must be greater than zero.")

        if sample_interval_s < 0:
            raise ValueError("sample_interval_s cannot be negative.")

        values = []
        deadline = time.monotonic() + integration_time_s
        last_error = None

        while time.monotonic() < deadline:
            try:
                value = self.get_power()

                if math.isfinite(value):
                    values.append(value)
                elif not ignore_invalid:
                    raise PM100DError(
                        f"PM100D returned invalid power: {value}"
                    )

            except Exception as exc:
                last_error = exc

                if not ignore_invalid:
                    raise

            if sample_interval_s > 0:
                remaining = deadline - time.monotonic()

                if remaining > 0:
                    time.sleep(min(sample_interval_s, remaining))

        if not values:
            if last_error is not None:
                raise PM100DError(
                    "No valid PM100D power samples were collected."
                ) from last_error

            raise PM100DError(
                "No valid PM100D power samples were collected."
            )

        return sum(values) / len(values)

    # Compatibility name for your PLE experiment.
    get_average_power = average_power

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Close the PM100D connection."""
        if not self._connected:
            return

        try:
            result = self._lib.TLPM_close(self._session)
            self._check(result, "Closing PM100D")
        finally:
            self._connected = False
            self._session = c_ulong(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


if __name__ == "__main__":
    # Standalone connection test.
    with PM100D() as pm:
        print("Connected resource:", pm.get_resource_name())

        wavelength = pm.set_wavelength(1034.6)
        print("Configured wavelength:", wavelength, "nm")
        print("Reported wavelength:", pm.get_wavelength(), "nm")

        power = pm.get_power()
        print("Instantaneous power:", power, "W")

        average = pm.average_power(
            integration_time_s=0.5,
            sample_interval_s=0.01,
        )
        print("Average power:", average, "W")