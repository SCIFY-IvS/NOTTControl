/// macie_lib.h
////////////////////////////////////////////////////////////////////////////////
//
// Copyright 2018, Jarron Leisenring, All rights reserved.
//

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <exception>

#include <string.h>
#include <sstream>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <ctype.h>

#include <math.h>
#include <time.h>
#include <signal.h>

#include <sys/time.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/signal.h>

#include <map>
#include <vector>
#include <iterator>

#include "macie.h"
#include "fitsio.h"
#include "dirent.h"

#ifndef MACIELIB_H
#define MACIELIB_H

// TRUE/FALSE definitions
#ifndef FALSE
#define FALSE 0
#endif
#ifndef TRUE
#define TRUE (!(FALSE))
#endif


//------------------------------------------------------------------------
// Allowed values for various mode settings
//------------------------------------------------------------------------

// H1/2/4RG
typedef enum CAMERA_TYPE
{
  CAMERA_TYPE_H1RG,
  CAMERA_TYPE_H2RG,
  CAMERA_TYPE_H4RG
} CAMERA_TYPE;

// Fast or Slow pixel rate
typedef enum CAMERA_MODE
{
  CAMERA_MODE_SLOW,
  CAMERA_MODE_FAST
} CAMERA_MODE;

typedef enum LOG_LEVEL
{
  LOG_DEBUG,
  LOG_INFO,
  LOG_WARNING,
  LOG_ERROR,
  LOG_NONE
} LOG_LEVEL;

//------------------------------------------------------------------------
// All MACIE settings and parameters
//------------------------------------------------------------------------

// Register address info and value
// 3-element array describing reg address, bit start, bit end
typedef struct regInfo
{
  unsigned short addr;  // Register address
  unsigned short bit0;  // First (lowest) relevant bit
  unsigned short bit1;  // Last (highest) relevant bit
  unsigned int value;   // Value assigned to bits
} regInfo;

// This is the structure used to hold information about the MACIE and ASIC.
typedef struct MACIE_Settings
{
  LOG_LEVEL verbosity;              // Message log level

  // Detector type and mode inputs
  CAMERA_TYPE DetectorType;         // Detector type (H1RG,H2RG,H4RG)
  CAMERA_MODE DetectorMode;         // Fast or Slow readout Mode
  MACIE_Connection connection;      // MACIE connection input

  // Detector size populated after init
  unsigned int uiDetectorWidth;   // Full SCA width
  unsigned int uiDetectorHeight;  // Full SCA height

  // Config file inputs
  char MACIEFile[2048];             // MACIE register file
  char ASICFile[2048];              // ASIC microcode file
  char ASICRegs[2048];             // ASIC Register config file
  // File save info
  bool         bSaveData;           // Write FITS file to disk?
  std::string  saveDir;             // Directory to save FITS files
  std::string  filePrefix;          // Filename prefix: LMIR_YYYMMDD_*.fits
  unsigned int uiFileNum;           // Ramp file number for incrementing; only use for test data offset...

  // MACIE and ASIC card selection
  // Nominally updated during MACIE and ASIC init
  MACIE_CardInfo *pCard;            // pointer to CardInfo
  unsigned short numCards;          // Number of connected MACIESs
  unsigned long  handle;            // Handle of selected card (USB+MACIE0)
  unsigned char  avaiMACIEs;        // Available connected MACIEs
  unsigned char  slctMACIEs;        // Selected MACIE (currently always MACIE0)
  bool           bMACIEslot1;       // Load firmware from MACIE Slot1?
  unsigned char  avaiASICs;         // Available connected ASICs
  unsigned char  slctASICs;         // Selected ASIC (currently always ASIC0)
  
  unsigned int   clkRateM;          // Value of MACIE clock driver (MHz)
  unsigned int   clkRateMDefault;   // Default MACIE clock driver (MHz)
  unsigned short clkPhase;          // Value of phase shift on MACIE register
  unsigned short clkPhaseDefault;   // Default phase shift value to set on init
  unsigned int   pixelRate;         // Detector pixel rate (kHz)

  unsigned int   uiNumCoadds;       // # of Ramp/Int to average
  unsigned int   uiNumSaves;        // # of final saved ramps
  unsigned int   uiNumGroups_max;   // Max number of Groups in a ramp

  double         frametime_ms;      // Storage for frametime information
  double         ramptime_ms;       // Storage for ramptime information

  short          nBuffer;           // # of local frame buffers to store data
  // unsigned long  nBytesMin;         // Minimum number of bytes allowed to command detector
  unsigned long  nBytesMax;         // Maximum number of total bytes allowed for mem allocation
  unsigned long  nPixBuffMin;       // Minimum number of 16-bit pixels for a given buffer
  unsigned long  nPixBuffMax;       // Maximum number of 16-bit pixels for a given buffer (single ramp restriction)
  unsigned long  nPixBuffer;        // Number of pixels currently set for a given buffer size
  bool           bUseSciDataFunc;  // Use MACIE_ReadUSBScienceData() instead of MACIE_ReadUSBScienceFrame()

  // MACIE error counters
  unsigned short errArr[MACIE_ERROR_COUNTERS];

  // MACIE firmware version info
  // Values should be displayed as HEX for human readable
  unsigned int firmwareVersion;
  unsigned int firmwareMonthDay;
  unsigned int firmwareYear;

  // Assembly Code values mapped as a dictionary
  std::map<std::string, regInfo> RegMap;

  // Is STRIPE mode allowed?
  bool bStripeModeAllowed;
  bool bStripeMode;

  // Pixel clocking scheme for full frame and subarray window
  // Normal (0) or Enhanced (1)
  // Only here until Enhanced+Window works correctly in future ASIC microcode
  unsigned int ffPixelClkScheme;
  unsigned int winPixelClkScheme;

  // Set for offline code development and testing
  bool offline_develop;
  std::map<std::string, regInfo> RegAllASIC; // Only used for testing

} MACIE_Settings;

extern void delay(int ms);
extern ushort subtract_ushort(ushort x, ushort y);

// Parameter structure handling
extern bool SettingsCheckNULL(MACIE_Settings *ptUserData);
extern bool create_param_struct(MACIE_Settings *ptUserData, LOG_LEVEL verbosity);

// MACIE interface and init
extern bool CheckInterfaces(MACIE_Settings *ptUserData);
extern bool GetHandleUSB(MACIE_Settings *ptUserData);
extern bool GetHandleGigE(MACIE_Settings *ptUserData);
extern bool GetAvailableMACIEs(MACIE_Settings *ptUserData);
extern bool GetAvailableASICs(MACIE_Settings *ptUserData);
extern bool ASIC_Defaults(MACIE_Settings *ptUserData);
extern bool InitializeASIC(MACIE_Settings *ptUserData);
extern bool LoadASIC(MACIE_Settings *ptUserData);
extern bool ReconfigureASIC(MACIE_Settings *ptUserData);

extern unsigned long GetMemAvailable(MACIE_Settings *ptUserData);
extern void SetNBuffer(MACIE_Settings *ptUserData, short nBuffer);
extern void SetBuffSize(MACIE_Settings *ptUserData, unsigned int PixBuffer);
extern unsigned long CalcBuffSize(MACIE_Settings *ptUserData);
extern unsigned long CalcBuffSize(MACIE_Settings *ptUserData, unsigned int mode);
extern short CalcNBuffers(MACIE_Settings *ptUserData);
extern void ConfigBuffers(MACIE_Settings *ptUserData);
extern bool VerifyBuffers(MACIE_Settings *ptUserData);
extern double MemBufferFrac(MACIE_Settings *ptUserData);

// MACIE power and voltage settings
#define MACIE_PWR_DAC_SIZE 38
#define MACIE_PWR_CTRL_SIZE 41
extern bool GetVoltages(MACIE_Settings *ptUserData, float vArr[]);
extern bool GetPower(MACIE_Settings *ptUserData, bool pArr[]);
extern bool GetPowerASIC(MACIE_Settings *ptUserData, bool *bEn);
extern bool SetPowerASIC(MACIE_Settings *ptUserData, bool bEn);
extern bool SetLED(MACIE_Settings *ptUserData, unsigned int set_val);

extern bool AcquireDataUSB(MACIE_Settings *ptUserData, bool externalTrigger);
extern bool AcquireDataGigE(MACIE_Settings *ptUserData, bool externalTrigger);
extern void HaltCameraAcq(MACIE_Settings *ptUserData);
extern bool DownloadAndSaveAllUSB(MACIE_Settings *ptUserData);
extern bool DownloadRampUSB(MACIE_Settings *ptUserData, unsigned short pData[], long framesize, 
                            long nframes_save, int triggerTimeout, int wait_delta);
extern bool DownloadRampUSB_Frame(MACIE_Settings *ptUserData, unsigned short pData[], long framesize,
                                 long nframes_save, int triggerTimeout, int wait_delta);
extern bool DownloadRampUSB_Data(MACIE_Settings *ptUserData, unsigned short pData[], long framesize,
                                 long nframes_save, int triggerTimeout, int wait_delta);
extern bool DownloadDataUSB(MACIE_Settings *ptUserData, unsigned short pData[], long SIZE, unsigned short timeout);
extern bool DownloadFrameUSB(MACIE_Settings *ptUserData, unsigned short pData[], long SIZE, unsigned short timeout);
extern bool CloseUSBScienceInterface(MACIE_Settings *ptUserData);
extern bool CloseGigEScienceInterface(MACIE_Settings *ptUserData);
extern bool WriteFITSFile(MACIE_Settings *ptUserData, unsigned short *pData, char *fileName);
extern bool WriteFITSRamp(void *pData, std::vector <long> naxis, int bitpix, std::string filename);
extern void exposure_test_data(MACIE_Settings *ptUserData, unsigned short pData[], long SIZE);

// MACIE phase shifting
extern bool GetMACIEPhaseShift(MACIE_Settings *ptUserData);
extern bool SetMACIEPhaseShift(MACIE_Settings *ptUserData, unsigned short clkPhase);
extern bool ToggleMACIEPhaseShift(MACIE_Settings *ptUserData, bool enable);
extern bool FindOptimalPhaseShift(MACIE_Settings *ptUserData, ushort val_start, ushort val_end);
extern bool GetMACIEClockRate(MACIE_Settings *ptUserData);
extern bool SetMACIEClockRate(MACIE_Settings *ptUserData, unsigned int clkRateM);

// ASIC register reading
extern bool ReadASICReg(MACIE_Settings *ptUserData, unsigned short addr, unsigned int *val);
extern bool ReadASICBits(MACIE_Settings *ptUserData, regInfo *reg, unsigned int *val);
extern bool ReadASICBlock(MACIE_Settings *ptUserData, unsigned short addr, int nreg, unsigned int *val);
extern bool readASICconfig(MACIE_Settings *ptUserData, unsigned short addr, int nreg);


// ASIC reg writing
extern bool WriteASICReg(MACIE_Settings *ptUserData, unsigned short addr, unsigned int val);
extern bool WriteASICBits(MACIE_Settings *ptUserData, regInfo *reg);
extern bool WriteASICBlock(MACIE_Settings *ptUserData, unsigned short addr, int nreg,
									 	       unsigned int *val);

// Storing ASIC settings locally
extern regInfo gen_regInfo(unsigned short addr, unsigned short bit0, unsigned short bit1,
                           unsigned int value);
extern bool initRegMap(MACIE_Settings *ptUserData);
extern bool GetASICSettings(MACIE_Settings *ptUserData);
extern bool SetASICParameter(MACIE_Settings *ptUserData, std::string addr_name, unsigned int val);
extern bool GetASICParameter(MACIE_Settings *ptUserData, std::string addr_name, unsigned int *val);

// Convenience functions for various ASIC parameters
extern unsigned int ASIC_Generic(MACIE_Settings *ptUserData, std::string addr_name,  bool bSet, unsigned int val);
extern unsigned int ASIC_NResets(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_NReads(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_NDrops(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_NGroups(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_NRamps(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_NCoadds(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_NSaves(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
// Window/Subarray settings
extern bool verify_subarray_size(MACIE_Settings *ptUserData, uint nx, uint ny, unsigned long nybtes_ramp);
extern void burst_stripe_set_ffidle(MACIE_Settings *ptUserData);
extern bool ypix_burst_stripe(MACIE_Settings *ptUserData, unsigned int *ypix, bool bSet);
extern bool ASIC_STRIPEMode(MACIE_Settings *ptUserData, bool bSet, bool bVal);
extern unsigned int ASIC_WinHorz(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_WinVert(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_getX1(MACIE_Settings *ptUserData);
extern unsigned int ASIC_getX2(MACIE_Settings *ptUserData);
extern unsigned int ASIC_getY1(MACIE_Settings *ptUserData);
extern unsigned int ASIC_getY2(MACIE_Settings *ptUserData);
extern unsigned int ASIC_setX1(MACIE_Settings *ptUserData, unsigned int val);
extern unsigned int ASIC_setX2(MACIE_Settings *ptUserData, unsigned int val);
extern unsigned int ASIC_setY1(MACIE_Settings *ptUserData, unsigned int val);
extern unsigned int ASIC_setY2(MACIE_Settings *ptUserData, unsigned int val);
extern unsigned int ASIC_NumOutputs(MACIE_Settings *ptUserData);
extern unsigned int ASIC_NumOutputs(MACIE_Settings *ptUserData, bool bFullFrame);
extern unsigned int ASIC_NumOutputs(MACIE_Settings *ptUserData, bool bSet, unsigned int val);

// More frame info
extern unsigned int exposure_nframes(MACIE_Settings *ptUserData, bool include_all);
extern unsigned int exposure_xpix(MACIE_Settings *ptUserData);
extern unsigned int exposure_ypix(MACIE_Settings *ptUserData);
extern unsigned int exposure_frametime_pix(MACIE_Settings *ptUserData);
extern double exposure_frametime_ms(MACIE_Settings *ptUserData);
extern double exposure_grouptime_ms(MACIE_Settings *ptUserData);
extern double exposure_ramptime_ms(MACIE_Settings *ptUserData);
extern double exposure_inttime_ms(MACIE_Settings *ptUserData);
extern double exposure_efficiency(MACIE_Settings *ptUserData);

extern bool set_exposure_settings(MACIE_Settings *ptUserData, bool bSave,
    uint ncoadds, uint nsaved_ramps, uint ngroups, uint nreads, uint ndrops, uint nresets);
extern bool set_frame_settings(MACIE_Settings *ptUserData, bool bHorzWin, bool bVertWin,
    uint x1, uint x2, uint y1, uint y2);
extern bool calc_ramp_settings(MACIE_Settings *ptUserData, double tint_ms, int ngmax,
    uint *ngroups, uint *ndrops, uint *nreads);

// ASIC Inputs, Gain, Cap Comp, and low-frequency filter
extern unsigned int ASIC_Inputs(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_Gain(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_CapComp(MACIE_Settings *ptUserData, bool bSet, unsigned int val);
extern unsigned int ASIC_FiltPole(MACIE_Settings *ptUserData, bool bSet, unsigned int val);

extern float ConvertDACToV(unsigned int dac_setting);
extern unsigned int ConvertVToDAC(float volts);

// Error counters
extern unsigned int TotalErrorCounts(MACIE_Settings *ptUserData);
extern bool ResetErrorCounters(MACIE_Settings *ptUserData);
extern bool GetErrorCounters(MACIE_Settings *ptUserData, bool bVerb);

// Some utility function
extern std::string strip_white(const std::string &input);
extern std::string strip_comments(const std::string &input, const std::string &delimiters);

extern void verbose_printf(LOG_LEVEL level, MACIE_Settings *ptUserData, const char *format, ... );
extern void set_verbose(MACIE_Settings *ptUserData, LOG_LEVEL level);
extern LOG_LEVEL get_verbose(MACIE_Settings *ptUserData);

extern const char *convert_camera_type_str(CAMERA_TYPE type);
extern CAMERA_TYPE convert_camera_type(const char *pcDetectorType);
extern const char *convert_camera_mode_str(CAMERA_MODE mode);
extern CAMERA_MODE convert_camera_mode(const char *pcDetectorMode);
extern const char *convert_log_type_str(LOG_LEVEL level);
extern LOG_LEVEL convert_log_type(const char *pcLevel);

extern bool initASICRegs_testing(MACIE_Settings *ptUserData);

#endif // MACIELIB_H

//------------------------------------------------------------------------
// MACIE API functions
//------------------------------------------------------------------------
// MACIE_LibVersion();
// MACIE_Init();
// MACIE_Free();
// MACIE_Error();
//
// MACIE_CheckInterfaces();
// MACIE_GetHandle();
//
// MACIE_GetAvailableMACIEs();
// MACIE_GetAvailableASICs();
//
// MACIE_ReadMACIEReg();
// MACIE_WriteMACIEReg();
// MACIE_ReadMACIEBlock();
// MACIE_WriteMACIEBlock();
//
// MACIE_loadMACIEFirmware();
// MACIE_DownloadMACIEFile();
// MACIE_DownloadLoadfile();
//
// MACIE_WriteASICReg();
// MACIE_ReadASICReg();
// MACIE_WriteASICBlock();
// MACIE_ReadASICBlock();
// MACIE_DownloadASICFile();
//
// MACIE_ClosePort();
// MACIE_GetErrorCounters();
// MACIE_ResetErrorCounters();
//
// MACIE_SetMACIEPhaseShift();
// MACIE_GetMACIEPhaseShift();
//
// MACIE_ConfigureCamLinkInterface();
// MACIE_ConfigureGigeScienceInterface();
// MACIE_ConfigureUSBScienceInterface();
//
// MACIE_AvailableScienceData();
// MACIE_AvailableScienceFrames();
//
// MACIE_ReadGigeScienceFrame();
// MACIE_ReadGigeScienceData();
// MACIE_ReadCamlinkScienceFrame();
// MACIE_ReadUSBScienceFrame();
// MACIE_ReadUSBScienceData();
//
// MACIE_WriteFitsFile();
//
// MACIE_CloseCamlinkScienceInterface();
// MACIE_CloseGigeScienceInterface();
// MACIE_CloseUSBScienceInterface();
//
// MACIE_SetVoltage();
// MACIE_GetVoltage();
// MACIE_EnablePower();
// MACIE_DisablePower();
// MACIE_SetPower();
// MACIE_GetPower();
//
// MACIE_SetTelemetryConfiguration();
// MACIE_GetTelemetryConfiguration();
// MACIE_GetTelemetry();
// MACIE_GetTelemetrySet();
// MACIE_GetTelemetryAll();
