/*

CLI.cpp is a stripped down CLI version of the example GUI provided by Jobin Yvon in their SDK.

To compile:
- Find the Examples directory of the SDK installation. This is probably something like:
    C:\Program Files (x86)\Jobin Yvon\SDK\Examples\C++\MonoCCD_Cpp_2010
- Open the vcxproj file in the oldest version of Visual Studio you have. I used Visual Studio 2019.
- Take these three files --- CLI.h, CLI.cpp, and JYDeviceSink.h --- and plop them into the Resource Files (.cpp) or Header Files (.h) directory
- Comment out everything in MonoCDD_Cpp_2010Dlg.cpp after the last "#endif" near the very top of the file (or just delete it maybe?)
- Find the JYSystemLib.dll and JYConfigBrowserComponent.dll files and #import them (shown below) 
- Make sure these two .dll's were registered using regsvr32 or whatever the 64-bit version is called (using SYSWO64 or something)
- I don't know if this does anything, but make sure you have all the ATL and MTF (MTC??) packages installed. Do this using
  the Visual Studio Installer and clicking "Modify" for your VS installation.
- Make sure ole32.lib and oleaut32.lib are included in the linker. I forget how to do this but it's in Properties -> C/C++ -> Linker, I think?
- pray. google any compile errors
*/

#pragma once
// included in JYDeviceSink so that it doesn't yell at me
#import "C:\Program Files (x86)\Jobin Yvon\Common\JY Components\JYSupport\JYSystemLib.dll" raw_interfaces_only, raw_native_types, no_namespace, named_guids 
#import "C:\Program Files (x86)\Jobin Yvon\Common\JY Components\JYSupport\JYConfigBrowserComponent.dll" raw_interfaces_only, raw_native_types, no_namespace, named_guids 