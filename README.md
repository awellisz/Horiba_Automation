# Horiba Automation

This repo is a collection of some of the code used to automate data collection and instrument control with a Horiba iHR-550 spectrometer and SynapsePlus CCD (without using LabSpec6 or other proprietary software). This code allows you to change the center wavelength and diffraction grating of the spectrometer as well as capture spectra with specified settings (integration time, binning, ROI). The details for how to use this code are found in `horiba_driver.py`. 

Resources online for this are pretty thin, and the Jobin Yvon SDK manual is light on the details when it comes to setting this sort of thing up for the first time. The most important files here are `Horiba_CLI.exe` and `horiba_driver.py`. The former is a command line interface which can communicate with the iHR-550 and the SynapsePlus imaging CCD, and the latter is a Python wrapper to integrate it into the rest of our instrument control software. 

`Horiba_CLI.exe` will not work if you haven't installed the Jobin Yvon SDK, which you have to get from Horiba. Also, it uses a hard-coded SDK installation path, so if that installation path happens to be different for whatever reason, you will have to modify the relevant line in `CLI.h` and re-compile it yourself.

## Compiling CLI.cpp

You will need `CLI.cpp`, `CLI.h`, `JYDeviceSink.cpp`, and `JYDeviceSink.h` from this repo. The Jobin Yvon SDK must be installed. This has only been tested on Windows 10 using the 2023 (?) version of the JY SDK.

CLI.cpp is based on the example GUI code provided by Jobin Yvon in their SDK and the SDK manual. The code appears to have been written in 2001 and was last compiled in 2010, so it can be tricky to get everything to work. The following is a very rough guide on how you might try to compile this code yourself. It took a lot of trial and error, and this is what worked for us:

- Find the GUI control example project can be found in the SDK installation directory. In our case, it's in `C:\Program Files (x86)\Jobin Yvon\SDK\Examples\C++\MonoCCD_Cpp_2010` ("MonoCCD" controls both the monochromator and the CCD). Make a copy of this folder as a backup in case something goes wrong.
- Open the .vcxproj file in the oldest version of Visual Studio you have (for good measure). I used VS2019. It's probably possible to make a new project from scratch, but this way a lot of the settings are already set correctly for the project.
- Place `CLI.cpp` and `JYDeviceSink.cpp` into the Resource Files directory and `CLI.h` and `JYDeviceSink.h` into the Header Files directory.
- Comment out everything in `MonoCCD_Cpp_2010Dlg.cpp` after the last `#endif` near the very top of the file. You might be able to just delete the file entirely, but I got some warnings and didn't want to deal with them.
- Find the `JYSystemLib.dll` and `JYConfigBrowserComponent.dll` files from your SDK installation. On our system, these live in `C:\Program Files (x86)\Jobin Yvon\Common\JY Components\JYSupport\`. 
- Run command prompt as administrator and register the two .dll files using `%systemroot%\SysWoW64\regsvr32 <full path of the DLL>`. Note that the files provided by the JY SDK are 32-bit DLL's (or at least they were for us), but if you're on Windows 10 you have a 64-bit operating system, so you'll have to register using the 32-bit version of regsvr32 which is at `%systemroot%\SysWoW64\regsvr32.exe` rather than just running `regsvr32`.
- You might get some errors related to ATL and/or MTF packages. Run the Visual Studio Installer, click "Modify" for your Visual Studio installation and make sure you have the right ATL and MTF packages installed to satisfy the errors.
- Make sure `ole32.lib` and `oleaut32.lib` are included in the linker for the VS project. This is probably in Properties > C/C++ > Linker. 

## nspyre integration

All of the code in the nspyre folder is written to work with our [nspyre](https://nspyre.readthedocs.io/en/latest/) setup. The code is very ad hoc and will almost certainly not work out of the box. `take_single_spectra.py` includes `SingleSpectraMeasurement` which has all the code you need to understand how you might run an experiment that uses `horiba_driver.py`. The rest is just there for completeness.

Using this code with nspyre of course requires adding the driver to the instrument server (assuming it's in a folder called `/drivers/horiba/` relative to `inserv.py`) in the usual nspyre way:
`inserv.add('horiba', HERE / 'drivers' / 'horiba' / 'horiba_driver.py', 'Horiba')`
and adding the widgets to the nspyre MainWidget.

## Quirks of the code

As mentioned in some code comments, the SDK always appends something like `_0001_AREA1_1` to the end of a filename (e.g. if you try to save to `spectrum1.txt`, it will save to `spectrum1_0001_AREA1_1.txt` instead). Perhaps this can be resolved by messing around with the multi area acquisition. You can fix this pretty easily with automatic file renaming whenever you take a spectrum.

Also, `CLI.cpp` is entirely single-threaded, and acquisitions can't be stopped halfway through. Doing this in a roundabout way by force-quitting the .exe can cause problems that you'll have to physically restart the spectrometer to fix. You can probably change this to run multi-threaded, but I couldn't get it to work properly, and single-threaded operation is fine for our use case, since we can run the .exe in its own thread via nspyre. 

Lots of functionality, including changing the monochromator slit widths or mirror positions, calibration, and opening/closing the shutter, has not been implemented. You'll have to use LabSpec6 or implement it yourself in CLI.cpp.
 
Controlling the spectrometer with this code can sometimes cause issues if LabSpec6 is also open on the computer.
