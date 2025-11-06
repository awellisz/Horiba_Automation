"""
Driver to control the Horiba iHR 550 spectrometer and
SynapsePlus CCD camera.

This is a Python wrapper around `Horiba_CLI.exe`, which 
is a stripped-down version of MonoCCD_Cpp_2010Dlg provided as an 
example project for the Jobin Yvon SDK. 

Adding any additional functionality (e.g., changing spectrometer
slit widths or mirror positions, calibration, opening shutter)
has to be done manually in LabSpec6 or implemented by yourself 
in CLI.cpp and recompiled.

A. Wellisz 2025-10

KNOWN ISSUES:
- Sometimes (not always) causes problems if LabSpec6 is open
- Filenames always have "_0001_AREA1_1" appended to them. This is dealt with in the gui
- Acquisition can't be stopped midway since everything is single-threaded

The filename issue can be fixed after the fact pretty straightforwardly
using something like the following, where `full_path` is the desired
filename that was passed into `capture_spectrum`:

```
full_path_JY = full_path[:-len('.txt')] + '_0001_AREA1_1.txt'
os.rename(full_path_JY, full_path)
```

"""

import subprocess

class Horiba:
    """This class controls both the SynapsePlus CCD and the iHR 550 Spectrometer"""

    def __init__(self, exe_path = r"C:\Table4-Code\nspyre_ian\drivers\horiba\Horiba_CLI.exe", ystart=116, yend=136):
        """
        `exe_path` is the hard-coded path to the CLI exe.
        
        `ystart` and `yend` are the CCD ROI start/end values. This probably
        doesn't change very often. (Current value updated as of 2025-10-15)
        """
        self.exe_path = exe_path
        self.ystart = 116
        self.yend = 136

    def __enter__(self):
        return self
    
    def __exit__(self):
        pass

    def get_spec_info(self):
        """
        Gets monochromator info, parses key:value output into a dictionary.

        CLI command: 
            .\Horiba_CLI.exe --mono --info
        Example output:
            current_grating:300
            gratings: 1200 600 300
            front_entrance:0.08
            side_entrance:0
            front_exit:0
            side_exit:0
            wavelength:599.985
            wl_start:552.122
            wl_end:710.087
        """
        result = subprocess.run(
            [self.exe_path, "--mono", "--info"],
            capture_output=True, text=True, check=True
        )
        info = {}

        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line: 
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key == "gratings":
                # In theory a pGratingDensity in the SDK is a double, but in practice all 
                #  of our gratings are integers
                info["gratings"] = [int(x) for x in value.split()]
            elif key == "current_grating":
                info["current_grating"] = int(value)
            else:
                try:
                    info[key] = float(value)
                except ValueError:
                    info[key] = value

        return info

    def set_spec_wavelength(self, wavelength):
        """
        Sets the wavelength.

        Runs the following command, for example:
            .\CLI.exe --mono --wavelength 580.5

        For some reason, the wavelength set by the SDK is 31 nm off the actual center wavelength.
        """
        result = subprocess.run(
            [self.exe_path, "--mono", "--wavelength", str(wavelength-31)],  timeout=999999
        )
        return

    def set_spec_grating(self, grating):
        """
        Sets the spec grating.

        Runs (e.g.)
            .\Horiba_CLI.exe --mono --grating 1200
        """
        result = subprocess.run(
            [self.exe_path, "--mono", "--grating", str(float(grating))],  timeout=999999
        )
        return

    # Right now, CCD ROI (in y dir) should be approx 116 to 136
    def capture_spectrum(self, exposure_s = 1, outfile = None, spectra = True,
                         gain = "High Light", adc = " 50 kHz HS", xstart = 1, xend = 2048,
                         ystart = 1, yend = 512, xbin = 1, ybin = 512):
        """
        Capture one spectrum using the CCD.

        `exposure_s` (integration time) is in seconds.

        `outfile` must be an absolute path ending with the .txt file name.

        `gain` is a string and must exactly match one of the following:
            "High Light", "Best Dynamic", "High Sens.", "Ultimate Sens."
        `adc` is a string and must exactly match one of the following:
            " 50 kHz HS", "1.00 MHz HS", "3.00 MHz HS"
        (The space in " 50 kHz HS" is there on purpose. Blame Horiba)

        `xstart`, `xend`, `ystart`, `yend` are integers corresponding to
        the start/end values of the CCD region of interest. Make sure 
        these are within the bounds of the sensor (x=1-2048, y=1-512 for
        the SynapsePlus. Notably, these start at 1, not 0).
        All four must be provided to work properly, otherwise defaults to
        full chip.

        `xbin` and `ybin` are the (hardware) binning values in the X 
        and Y directions. (Default CLI behavior: ybin=512 if spectra mode).
        Both must be provided to work. (Note: 512 y binning works
        properly even if y ROI is less than 512 pixels tall)

        if `spectra=True`, output is 1D data (spectrum).
        if `spectra=False`, output is 2D image from CCD.

        Example command:
            .\Horiba_CLI.exe --ccd --spectra --exptime 2.5 --adc "1.00 MHz HS" --gain "High Sens." --roi 1 2048 116 132 --bin 1 512 --outfile "C:\Data\scratch\spec1.txt"
        """

        # Get ROI vals from object init
        ystart = self.ystart
        yend = self.yend

        args = [self.exe_path, "--ccd", "--exptime", str(exposure_s)]
        if spectra:
            args.append("--spectra")
        if outfile:
            args += ["--outfile", outfile]
        if gain:
            args += ["--gain", gain]
        if adc:
            args += ["--adc", adc]
        if xstart and xend and ystart and yend:
            args += ["--roi", str(xstart), str(xend), str(ystart), str(yend)]
        if xbin and ybin:
            args += ["--bin", str(xbin), str(ybin)]
        
        # Doesn't actually print anything to stdout so no need to store the result
        # Also, subprocess.run doesn't return until the .exe finishes running
        result = subprocess.run(args, capture_output = True, text = True, check = True, timeout=999999)

        # TODO: Detect if there was an error on stderr?

        return
        

if __name__ == "__main__":
    horiba = Horiba()
    info = horiba.get_spec_info()
    print(info)