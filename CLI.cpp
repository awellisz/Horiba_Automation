/*
This is a console program to control the Jobin Yvon spectrometer and CCD.
Written by A. Wellisz 2025-10-14.

Designed to be called externally by a Python program (for easy interfacing with nspyre experiments)
but you can also call it manually.

This lives in this particular directory because I am scared of changing anything to do with the
environment provided by the JY SDK. This is probably compilable (since the SDK paths are absolute), 
but it doesn't matter, since you can just take the resulting .exe and put it anywhere you want and 
it should still work.

Usage:

.\MonoCCD_Cpp_2010.exe --exptime TIME --adc NAME --gain NAME [--image | --spectra] 
                       --roi XSTART XEND YSTART YEND --bin XBIN YBIN
                       --outfile PATH

TIME is a float number of seconds
NAME is a string corresponding to the following options:
adc: " 50 kHz HS", "1.00 MHz HS", "3.00 MHz HS"
gain: "High Light", "Best Dynamic", "High Sens.", "Ultimate Sens."

(NB: THERE MUST BE A SPACE AT THE BEGINNING OF " 50 kHz HS". )

The quotation marks are important and spelling must be exact (but case-insensitive).

XSTART, XEND, YSTART, YEND are integers corresponding to the start/end values of the ROI. 
Make sure this is actually within the bounds of the camera sensor.

XBIN and YBIN are the binning in the X and Y directions.

The --image flag outputs an image (2D) data, the --spectra flag outputs a spectrum (1D).
--spectra automatically sets full y-binning across the given ROI.
--outfile specifies the path, e.g. "C:\Data\antos\251013_SDK_CCD_test\spectrum1.txt"

Example command:
.\MonoCCD_Cpp_2010.exe --exptime 10 --adc " 50 kHz HS" --gain "Ultimate Sens." --spectra --roi 1 2048 1 512 --bin 1 512 --outfile "C:\Data\antos\251013_SDK_CCD_test\spectrum1.txt"

*/

#include "stdafx.h" 
#include <windows.h>
#include <comdef.h>
#include <atlbase.h>
#include <string>
#include <vector>
#include <iostream>
#include <iomanip>
#include <chrono>
#include <thread>
#include <functional>


// This lives in C:\Program Files (x86)\Jobin Yvon\SDK\Examples\C++\MonoCCD_Cpp_2010_COMPILABLE_BACKUP
// This is basically just taking the logic from MonoCCD_Cpp_2010 and MonoCCD_Cpp_2010Dlg and converting it into a CLI app instead of a GUI

// Below is imported in CLI.h alkready
// #import "C:\Program Files (x86)\Jobin Yvon\Common\JY Components\JYSupport\JYSystemLib.dll" raw_interfaces_only, raw_native_types, no_namespace, named_guids 
// #import "C:\Program Files (x86)\Jobin Yvon\Common\JY Components\JYSupport\JYConfigBrowserComponent.dll" raw_interfaces_only, raw_native_types, no_namespace, named_guids 

#include "CLI.h"
#include "JYDeviceSink.h" // required for initialization event listeners

using std::wstring;
using std::wcout;
using std::wcerr;

/** HELPER FUNCTIONS **/

// For killing the program with an error message
static void die(wchar_t* msg, HRESULT hr = S_OK) {
    if (FAILED(hr)) {
        _com_error e(hr);
        fwprintf(stderr, L"%ls (0x%08X: %s)\n", msg, hr, e.ErrorMessage());
    }
    else {
        fwprintf(stderr, L"%s\n", msg);
    }
    ExitProcess(1);
}

// Check if strings a and b are equal (ignoring case, used for arg parsing)
static bool iequals(const std::wstring& a, const std::wstring& b) {
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); ++i) {
        if (towlower(a[i]) != towlower(b[i])) return false;
    }
    return true;
}

// For ATL connections (10 second timeout default)
// I have no idea how this function works. Thank you ChatGPT
static bool PumpUntil(const std::function<bool()>& done, DWORD timeout_ms = 10000) {
    const DWORD start = GetTickCount64();
    MSG msg{};
    while (!done()) {
        while (PeekMessage(&msg, nullptr, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessage(&msg); }
        if (GetTickCount64() - start >= timeout_ms) return false;
        MsgWaitForMultipleObjects(0, nullptr, FALSE, 10, QS_ALLINPUT);
    }
    return true;
}

// Callback sink target for IJYDeviceEvents (to satisfy IJYDeviceEvents in (modified) JYDeviceSink.h)
struct CliCallbacks : IJYDeviceEvents {
    bool ccdInitialized = false;
    bool criticalError = false;
    // we just need the initialized flag I think
    void ReceivedDeviceInitialized(long, IJYEventInfo*) override { ccdInitialized = true; }
    void ReceivedDeviceStatus(long, IJYEventInfo*) override {}
    void ReceivedDeviceUpdate(long, IJYEventInfo*) override {}
    void ReceivedDeviceCriticalError(long, IJYEventInfo*) override { criticalError = true; }
};

// command line args struct for controlling the ccd for captures
struct ccdArgs {
    double exptime = -1;
    std::wstring adc_name; // by display name
    std::wstring gain_name; // by display name
    bool image_mode = false; // true = image, false = spectrum (1D)
    int x_start = 1, x_end = 2048;
    int y_start = 1, y_end = 512;
    bool roi_given = false;
    int x_bin = 1, y_bin = 1;
    bool bin_given = false; 
    std::wstring outfile; // file path to save data
};

// command line args struct for spectrometer (monochromator) itself
struct monoArgs {
    bool set_wavelength = false;
    double wavelength_nm = -1;
    bool set_grating = false;
    double grating = 0.0;
    bool get_info = false; // true if user just wants mono info (don't change anything)
};

struct Args {
    bool ccd_mode = true; // true if we're running ccd instead of mono (i.e. true if --ccd flag is set, false if --mono flag)
    ccdArgs ccda;
    monoArgs monoa;
};

// parse command line arguments
static Args parse_args(int argc, wchar_t** argv) {
    Args a;
    if (argc == 1) { fwprintf(stderr, L"Missing args!\n"); ExitProcess(2); }
    
    // First arg after command itself should always be --ccd or --mono; check for this
    int i = 1;
    if (iequals(argv[i], L"--ccd")) {
        a.ccd_mode = true;
    }
    else if (iequals(argv[i], L"--mono")) {
        a.ccd_mode = false;
    }
    else {
        fwprintf(stderr, L"First flag must be --ccd or --mono\n");
        ExitProcess(2);
    }

    ++i;

    for (; i < argc; ++i) {
        std::wstring k = argv[i];

        if (a.ccd_mode) {
            if (k == L"--exptime" && (i + 1 < argc)) a.ccda.exptime = _wtof(argv[++i]);
            else if (k == L"--adc" && (i + 1 < argc)) a.ccda.adc_name = argv[++i];
            else if (k == L"--gain" && (i + 1 < argc)) a.ccda.gain_name = argv[++i];
            else if (k == L"--image") a.ccda.image_mode = true;
            else if (k == L"--spectra") a.ccda.image_mode = false;
            else if (k == L"--roi" && (i + 4 < argc)) {
                a.ccda.roi_given = true;
                a.ccda.x_start = _wtoi(argv[++i]); 
                a.ccda.x_end = _wtoi(argv[++i]);
                a.ccda.y_start = _wtoi(argv[++i]); 
                a.ccda.y_end = _wtoi(argv[++i]);
            }
            else if (k == L"--bin" && (i + 2 < argc)) {
                a.ccda.bin_given = true;
                a.ccda.x_bin = _wtoi(argv[++i]); 
                a.ccda.y_bin = _wtoi(argv[++i]);
            }
            else if (k == L"--outfile" && (i + 1 < argc)) a.ccda.outfile = argv[++i];
            else { 
                fwprintf(stderr, L"Unknown/incomplete arg: %s\n\n", k.c_str()); 
                ExitProcess(2); 
            }
        }
        else {
            if (k == L"--wavelength" && (i + 1 < argc)) {
                a.monoa.wavelength_nm = _wtof(argv[++i]);
                a.monoa.set_wavelength = true;
            }
            else if (k == L"--grating" && (i + 1 < argc)) {
                a.monoa.grating = _wtof(argv[++i]);
                a.monoa.set_grating = true;
            }
            else if (k == L"--info") {
                a.monoa.get_info = true;
            }
            else { 
                fwprintf(stderr, L"Unknown/incomplete arg: %s\n\n", k.c_str()); 
                ExitProcess(2); 
            }
        }
    }

    if (a.ccd_mode) {
        if (a.ccda.exptime <= 0) die(L"--exptime must be > 0");
    }
    else {
        if (a.monoa.wavelength_nm < 0 && a.monoa.set_wavelength) die(L"--wavelength <wavelength> is required for --mono");
    }
    
    return a;
}

// Run CCD capture (this function is called if --ccd flag is set)
static int run_ccd(ccdArgs& args) {
    HRESULT hr = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    if (FAILED(hr)) die(L"CoInitilizeEx failed", hr);

    {
        // Config browser
        // (CComPtr is safer than using bare points, automatically releases/avoids leaks etc)
        CComPtr<IJYConfigBrowerInterface> m_pConfigBrowser = nullptr;
        hr = CoCreateInstance(__uuidof(JYConfigBrowerInterface), nullptr, CLSCTX_INPROC_SERVER,
            __uuidof(IJYConfigBrowerInterface), (void**)&m_pConfigBrowser);
        if (FAILED(hr)) die(L"CoCreateInstance(ConfigBrowser) failed", hr);
        m_pConfigBrowser->Load();

        // Get CCD
        CComBSTR name, uid;
        m_pConfigBrowser->GetFirstCCD(&name, &uid);
        if (!uid || uid.Length() == 0) die(L"No CCDs found (GetFirstCCD returned empty UID)");

        // Create CCD object
        CComPtr<IJYCCDReqd> ccd;

        CLSID clsid;
        hr = CLSIDFromProgID(OLESTR("JYCCD.JYMCD"), &clsid);
        if (FAILED(hr)) die(L"CLSIDFromProgID(JYCCD.JYMCD) failed", hr);
        hr = CoCreateInstance(clsid, nullptr, CLSCTX_ALL, __uuidof(IJYCCDReqd), (void**)&ccd);
        if (FAILED(hr)) die(L"CoCreateInstance(IJYCCDReqd) failed", hr);

        CliCallbacks cb;
        CJYDeviceSink ccdSink(&cb, ccd);

        // Bind to the first UID and initialize
        ccd->put_Uniqueid(uid);
        ccd->Load();
        hr = ccd->OpenCommunications();
        if (FAILED(hr)) die(L"OpenCommunications failed to ccd");
        hr = ccd->Initialize(CComVariant(false), CComVariant(VARIANT_FALSE));
        if (FAILED(hr)) die(L"CCD init failed", hr);

        // Wait for initialization event (up to 5 seconds, should take <1 s)
        if (!PumpUntil([&] { return cb.ccdInitialized || cb.criticalError; }, 5000)) {
            die(L"Initialize timed out (no Initialized event)");
        }
        if (cb.criticalError) die(L"Critical error during Initialize");

        // If no ROI given, default to full CCD chip
        int xSizeFull = 0, ySizeFull = 0;
        {
            int x = 0, y = 0;
            hr = ccd->GetChipSize(&x, &y);
            if (FAILED(hr)) die(L"GetChipSize failed", hr);
            if (!args.roi_given) {
                args.x_start = 1;
                args.y_start = 1;
                args.x_end = x;
                args.y_end = y;
            }
            if (!args.bin_given) {
                args.x_bin = 1;
                // Full bin y range by default if in spectra mode
                args.y_bin = args.image_mode ? 1 : (args.y_end - args.y_start + 1);
            }
        }

        // Set params for the ccd
        ccd->SetDefaultUnits(jyutTime, jyuSeconds);
        hr = ccd->put_IntegrationTime(args.exptime);
        if (FAILED(hr)) die(L"put_IntegrationTime failed", hr);

        // Loop through the available gain settings until we find one that matches the input param
        if (!args.gain_name.empty()) {
            long gainToken = -1;
            CComBSTR gainStr;
            bool found = false;
            ccd->GetFirstGain(&gainStr, &gainToken);
            while (gainToken > -1) {
                std::wstring d(gainStr, gainStr.Length());
                // Check if our gain_name matches the CCD's gainStr
                if (iequals(d, args.gain_name)) {
                    found = true;
                    break;
                }
                // If not, keep looking
                ccd->GetNextGain(&gainStr, &gainToken);
            }
            if (!found) die(L"Gain not found");
            hr = ccd->put_Gain(gainToken);
            if (FAILED(hr)) die(L"put_Gain failed");
        }

        // Do the same as above but for ADC settings
        if (!args.adc_name.empty()) {
            long adcToken = 0;
            CComBSTR adcStr;
            bool found = false;
            ccd->GetFirstADC(&adcStr, &adcToken);
            while (adcToken > -1) {
                std::wstring d(adcStr, adcStr.Length());

                /*std::wcout << L"adcStr: \""
                    << static_cast<const wchar_t*>(adcStr)
                    << L"\"; args.adc_name: "
                    << args.adc_name << std::endl;*/

                if (iequals(d, args.adc_name)) {
                    found = true;
                    break;
                }
                ccd->GetNextADC(&adcStr, &adcToken);
            }
            if (!found) die(L"ADC not found", hr);
            hr = ccd->SelectADC((jyADCType)adcToken);
            if (FAILED(hr)) die(L"SelectADC failed", hr);
        }

        // Set acqusition format (image vs. spectrum)
        {
            jyCCDDataType format = args.image_mode ? JYMCD_ACQ_FORMAT_IMAGE : JYMCD_ACQ_FORMAT_SCAN;
            hr = ccd->DefineAcquisitionFormat(format, 1);
            if (FAILED(hr)) die(L"DefineAcquisitionFormat failed", hr);

            long xSize = (args.x_end - args.x_start) + 1;
            long ySize = (args.y_end - args.y_start) + 1;
            long ybin = args.image_mode ? args.y_bin : ySize; // spectra: bin full Y across ROI

            hr = ccd->DefineArea(1, args.x_start, args.y_start, xSize, ySize, args.x_bin, ybin);
            if (FAILED(hr)) die(L"DefineArea failed", hr);
        }

        // Check if CCD is ready
        VARIANT_BOOL ready = VARIANT_FALSE;
        ccd->get_ReadyForAcquisition(&ready);
        if (ready == VARIANT_FALSE) die(L"CCD not ready for acquisition");

        // single shot, non-threaded acqusition
        // Look into "DoAcquisition" in the SDK for threaded acq
        {
            VARIANT_BOOL busy = VARIANT_TRUE;
            hr = ccd->StartAcquisition(VARIANT_TRUE);
            if (FAILED(hr)) die(L"StartAcquisition failed", hr);

            while (busy == VARIANT_TRUE) {
                hr = ccd->AcquisitionBusy(&busy);
                if (FAILED(hr)) die(L"AcquisitionBusy failed", hr);
                Sleep(5);
            }

            CComPtr<IJYResultsObject> res;
            hr = ccd->GetResult(&res);
            if (FAILED(hr)) die(L"GetResult failed", hr);

            CComPtr<IJYDataObject> data;
            hr = res->GetFirstDataObject(&data);
            if (FAILED(hr)) die(L"GetFirstDataObject failed", hr);

            hr = data->put_FileType(jyTabDelimitted);
            if (FAILED(hr)) die(L"put_FileType(jyTabDelimitted) failed", hr);
            hr = data->Save(CComBSTR(args.outfile.c_str()));
            if (FAILED(hr)) die(L"Save failed", hr);
        }

        wcout << L"OK: saved to " << args.outfile << L"\n";
    }
    CoUninitialize();
    return 0;
}

// Changes monochromator settings; run if --mono flag is set
static int run_mono(monoArgs& args) {

    HRESULT hr = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    if (FAILED(hr)) die(L"CoInitilizeEx failed", hr);

    {
        // Config browser
        CComPtr<IJYConfigBrowerInterface> m_pConfigBrowser = nullptr;
        hr = CoCreateInstance(__uuidof(JYConfigBrowerInterface), nullptr, CLSCTX_INPROC_SERVER,
            __uuidof(IJYConfigBrowerInterface), (void**)&m_pConfigBrowser);
        if (FAILED(hr)) die(L"CoCreateInstance(ConfigBrowser) failed", hr);
        m_pConfigBrowser->Load();

        // Get monochromator
        CComBSTR name, monoID;
        m_pConfigBrowser->GetFirstMono(&name, &monoID);
        if (!monoID || monoID.Length() == 0) die(L"No spec found (GetFirstMono returned empty)");

        // Create mono object
        CComPtr<IJYMonoReqd> mono;

        CLSID clsid;
        hr = CLSIDFromProgID(OLESTR("JYMono.Monochromator"), &clsid);
        if (FAILED(hr)) die(L"CLSIDFromProgID(JYMono.Monochromator) failed", hr);
        hr = CoCreateInstance(clsid, nullptr, CLSCTX_ALL, __uuidof(IJYMonoReqd), (void**)&mono);
        if (FAILED(hr)) die(L"CoCreateInstance(IJYCCDReqd) failed", hr);

        CliCallbacks cb;
        CJYDeviceSink ccdSink(&cb, mono);

        // Bind to the first UID and initialize
        mono->put_Uniqueid(monoID);
        mono->Load();
        hr = mono->OpenCommunications();
        if (FAILED(hr)) die(L"OpenCommunications failed to mono");
        hr = mono->Initialize(CComVariant(false), CComVariant(VARIANT_FALSE));
        if (FAILED(hr)) die(L"CCD init failed", hr);

        // Wait for initialization event (up to 5 seconds, should take <1 s)
        if (!PumpUntil([&] { return cb.ccdInitialized || cb.criticalError; }, 5000)) {
            die(L"Initialize timed out (no Initialized event)");
        }
        if (cb.criticalError) die(L"Critical error during Initialize");

        // If user is just requesting info, print it to the console and exit
        if (args.get_info) {
            double current_grating;
            // Some annoying infrastructure to access the SafeArray of doubles stored in the out parameter all_gratings
            VARIANT all_gratings;
            hr = mono->GetCurrentGrating(&current_grating, &all_gratings);
            if (FAILED(hr)) die(L"GetCurrentGrating", hr);

            SAFEARRAY* psa;
            psa = all_gratings.parray;
            int num_gratings = psa->rgsabound->cElements;

            double* grating;
            hr = SafeArrayAccessData(psa, reinterpret_cast<void**> (&grating));

            wcout << L"current_grating:" << current_grating << L"\ngratings:";
            for (int i = 0; i < num_gratings; i++) {
                wcout << L" " << grating[i];
            }
            wcout << std::endl;

            double front_entrance, side_entrance, front_exit, side_exit;
            hr = mono->GetCurrentSlitWidth(Front_Entrance, &front_entrance);
            if (FAILED(hr)) die(L"GetCurrentSlitWidth", hr);
            hr = mono->GetCurrentSlitWidth(Side_Entrance, &side_entrance);
            hr = mono->GetCurrentSlitWidth(Front_Exit, &front_exit);
            hr = mono->GetCurrentSlitWidth(Side_Exit, &side_exit);

            wcout << L"front_entrance:" << front_entrance << L"\nside_entrance:" << side_entrance << L"\nfront_exit:" << front_exit << "\nside_exit:" << side_exit << std::endl;
            
            double curr_wavelength;
            hr = mono->GetCurrentWavelength(&curr_wavelength);
            if (FAILED(hr)) die(L"GetCurrentWavelength", hr);

            wcout << L"wavelength:" << curr_wavelength << std::endl;

            return 0;
        }

        // Set grating (for our iHR 550, the allowed values are 300.0, 600.0, 1200.0)
        if (args.set_grating) {
            wcout << L"Setting grating to " << args.grating << "\n";
            hr = mono->MovetoGrating(args.grating);
            if (FAILED(hr)) die(L"MovetoGrating failed", hr);
            VARIANT_BOOL busy = VARIANT_TRUE; 
            // Wait until setting grating is done (VERY IMPORTANT! AND CAN TAKE A WHILE)
            while (busy == VARIANT_TRUE) {
                hr = mono->IsBusy(&busy);
                if (FAILED(hr)) die(L"IsBusy failed", hr);
                Sleep(50); // wait 50 ms between checks
            }
        }

        // Set center wavelength 
        if (args.set_wavelength) {
            mono->SetDefaultUnits(jyutWavelength, jyuNanometers);
            hr = mono->MovetoWavelength(args.wavelength_nm);
            if (FAILED(hr)) die(L"MovetoWavelength failed", hr);
            // Wait until done
            VARIANT_BOOL busy = VARIANT_TRUE;
            while (busy == VARIANT_TRUE) {
                hr = mono->IsBusy(&busy);
                if (FAILED(hr)) die(L"IsBusy failed");
                Sleep(10); // this is usually fast
            }
        }

        // DEBUG: report final wavelength pos
        //double pos_nm = 0.0;
        //hr = mono->GetCurrentWavelength(&pos_nm);
        //if (FAILED(hr)) die(L"GetCurrentWavelength failed", hr);
        //wcout << L"Mono wl set to " << pos_nm << L" nm\n";
    }
    CoUninitialize();
    return 0;

}

int wmain(int argc, wchar_t* argv[]) {

    Args args = parse_args(argc, argv);

    if (args.ccd_mode) {
        return run_ccd(args.ccda);
    }
    else {
        return run_mono(args.monoa);
    }
}
