/// macie_lib.c
////////////////////////////////////////////////////////////////////////////////
//
// Copyright 2018, Jarron Leisenring, All rights reserved.
//

#include "macie_lib.h"

using std::map;
using std::string;
using std::vector;

// Timestamp in terms of microsec
typedef unsigned long long timestamp_t;
static timestamp_t get_timestamp()
{
    struct timeval now;
    gettimeofday(&now, NULL);
    return now.tv_usec + (timestamp_t)now.tv_sec * 1000000;
}

// Sleep for some number of millisec
void delay(int ms)
{
    // clock_t t0 = clock();
    // while ((clock() - t0) * 1000 / CLOCKS_PER_SEC < ms);
    usleep(1000 * ms);
}

bool SettingsCheckNULL(MACIE_Settings *ptUserData)
{
    // Is our structure ok?
    if (ptUserData == NULL)
    {
        fprintf(stderr, "User data structure is not valid\n");
        return false;
    }

    return true;
}

/// \brief create_param_struct Use this function to populate defaults for
///  variables within newly created ptUserData structure. For instance,
///  specify:  struct MACIE_Settings *ptUserData = new MACIE_Settings;
///  then:     create_param_struct(ptUserData, LOG_INFO);
/// \param ptUserData The user-set structure containing all the hardware parameters.
/// \param verbosity  Verbosity level to set things moving forward.
bool create_param_struct(MACIE_Settings *ptUserData, LOG_LEVEL verbosity)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    ptUserData->verbosity = verbosity;

    ptUserData->saveDir = "";
    ptUserData->filePrefix = "";

    // Initialize some values to defaults and others to 0
    ptUserData->pCard = new MACIE_CardInfo[8];
    ptUserData->numCards = 0;
    ptUserData->handle = 0;
    ptUserData->avaiMACIEs = 0;
    ptUserData->slctMACIEs = 1;
    ptUserData->bMACIEslot1 = true;
    ptUserData->avaiASICs = 0;
    ptUserData->slctASICs = 1;

    ptUserData->clkRateM = 0;
    ptUserData->clkRateMDefault = 0;
    ptUserData->clkPhase = 0;
    ptUserData->clkPhaseDefault = 0;
    ptUserData->pixelRate = 0;

    ptUserData->uiNumCoadds = 1;
    ptUserData->uiNumSaves = 0;
    ptUserData->uiNumGroups_max = 2; // Must be 2 or greater

    ptUserData->nBuffer = 20;                    // Default number of buffers
    ptUserData->nPixBuffer = 2048 * 2048;        // Default buffer size (in pixels)
    ptUserData->nPixBuffMin = 4 * 1024 * 1024;   // Min size (in pixels) for successful buffer allocation
    ptUserData->nPixBuffMax = 120 * 2048 * 2048; // Max size (in pixels) for a single buffer
    // ptUserData->nBytesMin       = 1024 * 1024;
    ptUserData->nBytesMax = UINT_MAX;    // Maximum number of total bytes allowed for mem allocation
    ptUserData->bUseSciDataFunc = false; // Use MACIE_ReadUSBScienceData() or MACIE_ReadUSBFrameData()?

    ptUserData->bSaveData = false;
    ptUserData->uiFileNum = 0;

    ptUserData->uiDetectorWidth = 0;
    ptUserData->uiDetectorHeight = 0;

    ptUserData->bStripeModeAllowed = false;
    ptUserData->bStripeMode = false;

    // Pixel clocking scheme for full frame and subarray window
    // Normal (0) or Enhanced (1)
    // Only here until Enhanced+Window works correctly in future ASIC microcode
    ptUserData->ffPixelClkScheme = 0;
    ptUserData->winPixelClkScheme = 0;

    ptUserData->offline_develop = false;

    // Set all error counters to 0
    std::fill_n(ptUserData->errArr, MACIE_ERROR_COUNTERS, 0);

    verbose_printf(LOG_DEBUG, ptUserData, "%s() returns true\n", __func__);
    // verbose_printf(LOG_INFO, ptUserData, "macieSerialNumber=%i\n", ptUserData->pCard[0].macieSerialNumber);

    return true;
}

void CardInfo_testing(MACIE_CardInfo **pCard)
{
    (*pCard)[0].macieSerialNumber = 1337;
    (*pCard)[0].bUART = false;
    (*pCard)[0].bGigE = false;
    (*pCard)[0].bUSB = true;
    strcpy((*pCard)[0].usbSerialNumber, "MACIE01337");
    (*pCard)[0].usbSpeed = 48;
}

string addr_name_hex(unsigned int addr)
{
    string addr_name = "0x";

    // Convert decimal addr to hex string
    std::stringstream ss;
    ss << std::hex << addr;
    addr_name.append(ss.str());

    return addr_name;
}

//  1. Check Interfaces: Detects and reports available MACIE cards and communication interfaces
////////////////////////////////////////////////////////////////////////////////
/// \brief CheckInterfaces Find all available MACIE cards that are connected to
///  the computer (directly or via network) and provide information about the
///  available interfaces (Camera Link, GigE and USB) to each card. Information
///  about each interface connection will be printed to console if
///  ptUserData.verbosity is high enough level.
/// \param ptUserData The user-set structure containing all the hardware parameters
bool CheckInterfaces(MACIE_Settings *ptUserData)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Check interfaces
    verbose_printf(LOG_INFO, ptUserData, "Checking MACIE Communication Interfaces....\n");
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_CheckInterfaces(0, NULL, 0, &ptUserData->numCards, &ptUserData->pCard) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_CheckInterfaces failed: %s\n", MACIE_Error());
            return false;
        }
    }
    else
    {
        ptUserData->numCards = 1;
        CardInfo_testing(&ptUserData->pCard);
    }
    verbose_printf(LOG_INFO, ptUserData, "numCards = %i\n", ptUserData->numCards);

    // Initialize pCard pointer shortcut
    MACIE_CardInfo *pCard = ptUserData->pCard;

    // Print information
    for (int i = 0; i < ptUserData->numCards; i++)
    {
        verbose_printf(LOG_INFO, ptUserData, "macieSerialNumber=%i\n", pCard[i].macieSerialNumber);
        // verbose_printf(LOG_INFO, ptUserData, "TEMP PRINT bUART=%i\n", pCard[i].bUART);
        // CamLink
        if (pCard[i].bUART == true)
        {
            verbose_printf(LOG_INFO, ptUserData, "  MACIE card connected to CamLink port\n");
            verbose_printf(LOG_INFO, ptUserData, "  serialPortName=%s\n", pCard[i].serialPortName);
        }
        // GigE
        if (pCard[i].bGigE == true)
        {
            verbose_printf(LOG_INFO, ptUserData, "  MACIE card connected to GigE port\n");
            verbose_printf(LOG_INFO, ptUserData, "  ipAddr=%i.%i.%i.%i\n",
                           static_cast<int>((pCard[i].ipAddr)[0]), static_cast<int>((pCard[i].ipAddr)[1]),
                           static_cast<int>((pCard[i].ipAddr)[2]), static_cast<int>((pCard[i].ipAddr)[3]));
        }
        // USB
        if (pCard[i].bUSB == true)
        {
            verbose_printf(LOG_INFO, ptUserData, "  MACIE card connected to USB port\n");
            verbose_printf(LOG_INFO, ptUserData, "  usbSerialNumber=%s\n", pCard[i].usbSerialNumber);
            verbose_printf(LOG_INFO, ptUserData, "  USBSpeed=%i\n", pCard[i].usbSpeed);
        }
    }

    verbose_printf(LOG_DEBUG, ptUserData, "  %s returns true\n", __func__);
    return true;
}

// 2. Get Handle (USB): Obtain a handle for the first available MACIE card connected by USB port
////////////////////////////////////////////////////////////////////////////////
/// \brief GetHandleUSB Set current communication interface with the input MACIE
///  serial number and USB connection. Grabs the first MACIE card it finds
///  connected to a USB connections. Sets a unique handle based on the MACIE
///  serial number and the MACIE_Connection type.
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool GetHandleUSB(MACIE_Settings *ptUserData)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // CardInfo was already set in CheckInterfaces
    //  if (ptUserData->offline_develop == false)
    //   {
    //     if (MACIE_CheckInterfaces(0, NULL, 0, &ptUserData->numCards, &ptUserData->pCard) != MACIE_OK)
    //     {
    //       verbose_printf(LOG_ERROR, ptUserData, "MACIE_CheckInterfaces failed: %s\n", MACIE_Error());
    //       return false;
    //     }
    //   }
    //   else
    //   {
    //     ptUserData->pCard = ptUserData->CardInfo);
    //   }

    MACIE_CardInfo *pCard = ptUserData->pCard;

    if (ptUserData->numCards == 0)
    {
        verbose_printf(LOG_ERROR, ptUserData, "No cards found: numCards = %i\n", ptUserData->numCards);
        return false;
    }

    ptUserData->handle = 0;

    // Cycle through each card to find USB and save info and handle
    for (int i = 0; i < ptUserData->numCards; i++)
    {
        if (pCard[i].bUSB == true)
        {
            verbose_printf(LOG_INFO, ptUserData, "Get handle for the interface of MACIE %i on USB port\n",
                           pCard[i].macieSerialNumber);

            if (ptUserData->offline_develop == false)
                ptUserData->handle = MACIE_GetHandle(pCard[i].macieSerialNumber, ptUserData->connection);
            else
                ptUserData->handle = 1;

            verbose_printf(LOG_DEBUG, ptUserData, "  %s returns true\n", __func__);
            return true;
        }
    }

    // If failed to find a USB, then handle=0
    if ((ptUserData->handle == 0) || (ptUserData->numCards == 0))
    {
        verbose_printf(LOG_ERROR, ptUserData, "  No USB cards found. Check interfaces.\n");
        verbose_printf(LOG_ERROR, ptUserData, "  numCards=%i, handle=%i\n",
                       ptUserData->numCards, ptUserData->handle);
        return false;
    }

    // Should never get here, but compiler was complaining about no return statement
    verbose_printf(LOG_DEBUG, ptUserData, "  %s returns true\n", __func__);
    return true;
}

// 2. Get Handle (gigE): Obtain a handle for the first available MACIE card connected by gigE port
////////////////////////////////////////////////////////////////////////////////
/// \brief GetHandleGigE Set current communication interface with the input MACIE
///  serial number and gigE connection. Grabs the first MACIE card it finds
///  connected to a gigE connections. Sets a unique handle based on the MACIE
///  serial number and the MACIE_Connection type.
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool GetHandleGigE(MACIE_Settings *ptUserData)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // CardInfo was already set in CheckInterfaces
    //  if (ptUserData->offline_develop == false)
    //   {
    //     if (MACIE_CheckInterfaces(0, NULL, 0, &ptUserData->numCards, &ptUserData->pCard) != MACIE_OK)
    //     {
    //       verbose_printf(LOG_ERROR, ptUserData, "MACIE_CheckInterfaces failed: %s\n", MACIE_Error());
    //       return false;
    //     }
    //   }
    //   else
    //   {
    //     ptUserData->pCard = ptUserData->CardInfo);
    //   }

    MACIE_CardInfo *pCard = ptUserData->pCard;

    if (ptUserData->numCards == 0)
    {
        verbose_printf(LOG_ERROR, ptUserData, "No cards found: numCards = %i\n", ptUserData->numCards);
        return false;
    }

    ptUserData->handle = 0;

    // Cycle through each card to find the ethernet connection and save info and handle
    for (int i = 0; i < ptUserData->numCards; i++)
    {
        if (pCard[i].bGigE == true) // TODO: maybe extend this to support more than one protocol at the same time?
        {
            verbose_printf(LOG_INFO, ptUserData, "Get handle for the interface of MACIE %i on USB port\n",
                           pCard[i].macieSerialNumber);

            if (ptUserData->offline_develop == false)
                ptUserData->handle = MACIE_GetHandle(pCard[i].macieSerialNumber, ptUserData->connection);
            else
                ptUserData->handle = 1;

            verbose_printf(LOG_DEBUG, ptUserData, "  %s returns true\n", __func__);
            return true;
        }
    }

    // If failed to find a USB, then handle=0
    if ((ptUserData->handle == 0) || (ptUserData->numCards == 0))
    {
        verbose_printf(LOG_ERROR, ptUserData, "  No USB cards found. Check interfaces.\n");
        verbose_printf(LOG_ERROR, ptUserData, "  numCards=%i, handle=%i\n",
                       ptUserData->numCards, ptUserData->handle);
        return false;
    }

    // Should never get here, but compiler was complaining about no return statement
    verbose_printf(LOG_DEBUG, ptUserData, "  %s returns true\n", __func__);
    return true;
}


////////////////////////////////////////////////////////////////////////////////
/// \brief GetAvailableMACIEs Detect Available MACIE cards: Reports how many
///  MACIE cards are connected at the port that is associated with the handle
///  stored in ptUserData.
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool GetAvailableMACIEs(MACIE_Settings *ptUserData)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    unsigned int val = 3;

    // avaiMACIEs consists of 8 bits indicating up to eight possible MACIE cards
    // slctMACIEs selects which MACIE to use
    verbose_printf(LOG_INFO, ptUserData, "Get available MACIE cards...\n");
    if (ptUserData->offline_develop == false)
        ptUserData->avaiMACIEs = MACIE_GetAvailableMACIEs(ptUserData->handle);
    else
        ptUserData->avaiMACIEs = 1;
    ptUserData->slctMACIEs = ptUserData->avaiMACIEs & 1; // Select MACIE0

    if (ptUserData->slctMACIEs == 0)
    {
        verbose_printf(LOG_ERROR, ptUserData, "  slctMACIEs = %i is invalid (avaiMACIEs = 0x%01x)\n",
                       ptUserData->slctMACIEs, ptUserData->avaiMACIEs);
        return false;
    }
    else if (ptUserData->offline_develop == false)
    {
        if (MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, 0x0300, &val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "  MACIE read h0300 failed: %s\n", MACIE_Error());
            return false;
        }
    }
    else
    {
        verbose_printf(LOG_INFO, ptUserData, "  MACIEs Available: MACIE%i\n",
                       (unsigned short)ptUserData->slctMACIEs - 1);
        verbose_printf(LOG_DEBUG, ptUserData, "  MACIE h0300 = 0x%04x\n", val);
    }

    verbose_printf(LOG_DEBUG, ptUserData, "  %s returns true\n", __func__);
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief GetAvailableASICs Detect Available ASIC cards: Reports how many
///  ASIC cards are connected through the same interface that is associated with
///  the handle stored in ptUserData.
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool GetAvailableASICs(MACIE_Settings *ptUserData)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // avaiASICs consists of 8 bits indicating up to eight possible ASIC cards (paried to 8 MACIEs)
    // slctASICs selects which ASIC to use
    verbose_printf(LOG_INFO, ptUserData, "Get available ASIC cards...\n");
    if (ptUserData->offline_develop == false)
        ptUserData->avaiASICs = MACIE_GetAvailableASICs(ptUserData->handle, 0);
    else
        ptUserData->avaiASICs = 1;
    ptUserData->slctASICs = ptUserData->avaiASICs & 1; // Select ASIC0

    if (ptUserData->slctASICs == 0)
    {
        verbose_printf(LOG_ERROR, ptUserData, "  slctASICs = %i is invalid (avaiASICs = 0x%1x)\n",
                       ptUserData->slctASICs, ptUserData->avaiASICs);
        return false;
    }
    else
    {
        verbose_printf(LOG_INFO, ptUserData, "  ASIC Selected: ASIC%i\n",
                       (unsigned short)ptUserData->slctASICs - 1);
    }

    verbose_printf(LOG_DEBUG, ptUserData, "  %s returns true\n", __func__);
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief ASIC_Defaults Set default values for various ASIC parameters
/// depending on the detector type.
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool ASIC_Defaults(MACIE_Settings *ptUserData)
{

    // Update intrinsic detector size
    if (ptUserData->DetectorType == CAMERA_TYPE_H1RG)
    {
        ptUserData->uiDetectorWidth = 1024;
        ptUserData->uiDetectorHeight = 1024;
        // ptUserData->nBuffer = ptUserData->DetectorMode==CAMERA_MODE_FAST ? 480 : 80;
        if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
        {
            SetASICParameter(ptUserData, "DetectorType", 1);
        }
    }
    else if (ptUserData->DetectorType == CAMERA_TYPE_H2RG)
    {
        ptUserData->uiDetectorWidth = 2048;
        ptUserData->uiDetectorHeight = 2048;
        // ptUserData->nBuffer = ptUserData->DetectorMode==CAMERA_MODE_FAST ? 100 : 20;
        if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
        {
            SetASICParameter(ptUserData, "DetectorType", 2);
        }
    }
    else if (ptUserData->DetectorType == CAMERA_TYPE_H4RG)
    {
        ptUserData->uiDetectorWidth = 4096;
        ptUserData->uiDetectorHeight = 4096;
        // ptUserData->nBuffer = ptUserData->DetectorMode==CAMERA_MODE_FAST ? 25 : 10;
        if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
        {
            SetASICParameter(ptUserData, "DetectorType", 4);
        }
    }
    else
    {
        verbose_printf(LOG_ERROR, ptUserData, "DetectorType not recognized.\n");
        return false;
    }

    // Reference Inputs
    if (ptUserData->DetectorMode == CAMERA_MODE_FAST) // Ground Fast
        ASIC_Inputs(ptUserData, true, 0x5a0a);

    // Extra pixels per line
    if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
    {
        SetASICParameter(ptUserData, "ExtraPixels", 0);
    }
    else
    {
        SetASICParameter(ptUserData, "ExtraPixels", 3);
    }

    // Extra lines per frame
    SetASICParameter(ptUserData, "ExtraLines", 0);

    // X and Y positions for full frame (???)
    ASIC_setX1(ptUserData, 0);
    ASIC_setX2(ptUserData, ptUserData->uiDetectorWidth - 1);
    ASIC_setY1(ptUserData, 0);
    ASIC_setY2(ptUserData, ptUserData->uiDetectorHeight - 1);

    // Update PixPerRow & RowsPerFrame for offline testing mode
    if (ptUserData->offline_develop == true)
    {
        unsigned int nout = ASIC_NumOutputs(ptUserData);
        unsigned int xtra_pix = ASIC_Generic(ptUserData, "ExtraPixels", false, 0);
        unsigned int xtra_lines = ASIC_Generic(ptUserData, "ExtraLines", false, 0);
        unsigned int ppr = ptUserData->uiDetectorWidth / nout + xtra_pix;
        unsigned int rpf = ptUserData->uiDetectorHeight + xtra_lines;
        if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
            SetASICParameter(ptUserData, "PixPerRow", ppr + 8);
        else
            SetASICParameter(ptUserData, "PixPerRow", ppr);
        SetASICParameter(ptUserData, "RowsPerFrame", rpf + 1);
    }

    // Fast Mode Gains and offsets
    if (ptUserData->DetectorMode == CAMERA_MODE_FAST)
    {
        ASIC_Gain(ptUserData, true, 5);
        ASIC_CapComp(ptUserData, true, 38);
        SetASICParameter(ptUserData, "VPreAmpRef1", 0x72c0);
    }

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief InitializeASIC Initialize ASIC associated with handle in ptUserData.
/// GetAvailableMACIEs must already have been run to populate slctMACIEs.
/// This function loads the MACIE firmware in the specified slot, downloads
/// the MACIE registers to the device, downloads
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool InitializeASIC(MACIE_Settings *ptUserData)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // MACIEFile = MACIE_Registers_Fast.mrf or MACIE_Registers_Slow.mrf
    // ASICFile = *.mcd

    unsigned int val = 0;

    // verbose_printf(LOG_INFO, ptUserData, "MACIE Library Version: %.1f\n", MACIE_LibVersion());
    verbose_printf(LOG_INFO, ptUserData, "Initializing with handle %i\n", ptUserData->handle);

    if ((unsigned short)ptUserData->slctMACIEs == 0)
    {
        verbose_printf(LOG_ERROR, ptUserData, "  No MACIEs available\n");
        return false;
    }

    ////////////////////////////////////////////////////////////////////////////////
    // step 1: load MACIE firmware from slot 1 (true) or slot 2 (false)
    verbose_printf(LOG_INFO, ptUserData, "Load MACIE firmware in slot %i...\n", ((ptUserData->bMACIEslot1 == true) ? 1 : 2));
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_loadMACIEFirmware(ptUserData->handle, ptUserData->slctMACIEs, ptUserData->bMACIEslot1, &val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "  Failed: %s\n", MACIE_Error());
            return false;
        }
        if (val != 0xac1e) // Confirm firmware is for SIDECAR ASIC (0xac1e)
        {
            verbose_printf(LOG_ERROR, ptUserData, "  Verification of MACIE firmware load failed: \n");
            verbose_printf(LOG_ERROR, ptUserData, "    Readback of hFFFB = 0x%04x\n", val);
            return false;
        }
        verbose_printf(LOG_INFO, ptUserData, "  Succeeded.\n");
        // Store firmware information
        MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, 0xfffd, &ptUserData->firmwareVersion);
        MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, 0xfffe, &ptUserData->firmwareMonthDay);
        MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, 0xffff, &ptUserData->firmwareYear);
    }
    else
    {
        ptUserData->firmwareVersion = 0x0310;
        ptUserData->firmwareMonthDay = 0x0101;
        ptUserData->firmwareYear = 0x2018;
    }
    verbose_printf(LOG_INFO, ptUserData, "Version = %04X MonthDay = %04X Year = %04X\n",
                   ptUserData->firmwareVersion, ptUserData->firmwareMonthDay, ptUserData->firmwareYear);

    ////////////////////////////////////////////////////////////////////////////////
    // step 2: download MACIE registers
    verbose_printf(LOG_INFO, ptUserData, "Downloading MACIE register %s\n", ptUserData->MACIEFile);
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_DownloadMACIEFile(ptUserData->handle, ptUserData->slctMACIEs, ptUserData->MACIEFile) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "  Failed: %s\n", MACIE_Error());
            return false;
        }
    }
    else
    {
        verbose_printf(LOG_INFO, ptUserData, "  Offline testing mode, skipping MACIE_DownloadMACIEFile().\n");
    }
    verbose_printf(LOG_INFO, ptUserData, "  Succeeded.\n");

    ////////////////////////////////////////////////////////////////////////////////
    // step 3: set default clkRate and clkPhase value stored in ptUserData
    verbose_printf(LOG_INFO, ptUserData, "Setting MACIE clock rate and phase parameters to default\n");
    if (GetMACIEClockRate(ptUserData) == false)
        return false;
    // if (SetMACIEClockRate(ptUserData, ptUserData->clkRateMDefault) == false)
    // 	return false;
    // verbose_printf(LOG_INFO, ptUserData, "Setting MACIE phase parameters to default\n");
    if (SetMACIEPhaseShift(ptUserData, ptUserData->clkPhaseDefault) == false)
        return false;

    ////////////////////////////////////////////////////////////////////////////////
    // step 4: Load ASIC firmware, download register values, and load some defaults
    if (LoadASIC(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "  LoadASIC: failed in %s\n", __func__);
        return false;
    }

    verbose_printf(LOG_INFO, ptUserData, "Initialization succeeded.\n");
    verbose_printf(LOG_DEBUG, ptUserData, "  %s returns true\n", __func__);
    verbose_printf(LOG_NONE, ptUserData, "\n"); // Print blank line
    return true;
}

bool LoadASIC(MACIE_Settings *ptUserData)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    ////////////////////////////////////////////////////////////////////////////////
    // step 1: reset science data error counters
    if (ResetErrorCounters(ptUserData) == false)
        return false;
    verbose_printf(LOG_INFO, ptUserData, "Reset error counters succeeded.\n");

    ////////////////////////////////////////////////////////////////////////////////
    // step 2: download ASIC file, for example ASIC mcd file
    //   This must happen before GetAvailableASICs in order to enable the ASIC
    //   command interface output buffer so the MACIE can communicate.
    verbose_printf(LOG_INFO, ptUserData, "Downloading ASIC microcode %s\n", ptUserData->ASICFile);
    verbose_printf(LOG_INFO, ptUserData, "  into ASIC%i\n", ptUserData->slctMACIEs - 1);
    delay(500);
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_DownloadASICFile(ptUserData->handle, ptUserData->slctMACIEs, ptUserData->ASICFile, true) != MACIE_OK) // m_asicIds
        {
            verbose_printf(LOG_ERROR, ptUserData, "  Failed: %s\n", MACIE_Error());
            return false;
        }
    }
    else
    {
        // Only perform this when testing.
        if (initASICRegs_testing(ptUserData) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "  initASICRegs_testing failed to complete.\n");
            return false;
        }
        verbose_printf(LOG_INFO, ptUserData, "  Offline testing mode, skipping MACIE_DownloadASICFile().\n");
    }

    ////////////////////////////////////////////////////////////////////////////////
    // step 3: get available ASICs
    if (GetAvailableASICs(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "GetAvailableASICs failed in %s\n", __func__);
        return false;
    }

    ////////////////////////////////////////////////////////////////////////////////
    // step 4: Save settings to ptUserData->RegMap
    if (GetASICSettings(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "  GetASICSettings failed to complete.\n");
        return false;
    }
    verbose_printf(LOG_INFO, ptUserData, "  GetASICSettings Succeeded.\n");

    ////////////////////////////////////////////////////////////////////////////////
    // step 5: set default values for various ASIC Settings
    if (ASIC_Defaults(ptUserData) == false)
        return false;
    verbose_printf(LOG_INFO, ptUserData, "ASIC_Defaults succeeded.\n");

    // TODO:
    // Pixel Clock scheme checks (i.e., Normal vs Enhanced) are necessary if there are
    // differences between full frame and subarray window clocking schemes. Normally
    // these would be the same, but there is a bug in the Slow Mode v5.0+ microcode
    // where Enhanced mode causes the columns to shift every other acquisition.
    // The shifted column then persists after switching back to full frame.
    // Something is wrong with the pixel timing code, so we always want window
    // mode to be operated in Normal
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    if (RegMap.count("PixelClkScheme") > 0)
    {
        unsigned int pixClk = 0;
        GetASICParameter(ptUserData, "PixelClkScheme", &pixClk);
        ptUserData->ffPixelClkScheme = pixClk;
        ptUserData->winPixelClkScheme = 0;
    }
    verbose_printf(LOG_INFO, ptUserData, "PixelClkScheme succeeded.\n");

    ////////////////////////////////////////////////////////////////////////////////
    // step 6: set_exposure_settings() also calls ReconfigureASIC()
    if (set_exposure_settings(ptUserData, true, 1, 1, 1, 1, 0, 1) == false)
        return false;

    verbose_printf(LOG_INFO, ptUserData, "LoadASIC succeeded.\n");
    verbose_printf(LOG_DEBUG, ptUserData, "  %s returns true\n", __func__);
    verbose_printf(LOG_NONE, ptUserData, "\n"); // Print blank line
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief ReconfigureASIC Reconfigure ASIC using h6900 register.
///  Update the user configuration registers (h4000-h402f) then initiate
///  a reconfiguration sequence by writing 0x8002 to h6900.
/// \param ptUserData The user-set structure containing all the hardware parameters
bool ReconfigureASIC(MACIE_Settings *ptUserData)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (ptUserData->DetectorMode == CAMERA_MODE_FAST)
    {
        // pseudo-reconfigure for Fast Mode to update output settings
        if (WriteASICReg(ptUserData, 0x6900, 0x8001) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "WriteASICReg failed in %s\n", __func__);
            return false;
        }
        delay(100);
        if (WriteASICReg(ptUserData, 0x6900, 0x8000) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "WriteASICReg failed in %s\n", __func__);
            return false;
        }
        delay(100);
        // Check that h6900=0x8000
        if (ptUserData->offline_develop == false)
        {
            unsigned int regval = 0;
            if (ReadASICReg(ptUserData, 0x6900, &regval) == false)
            {
                verbose_printf(LOG_ERROR, ptUserData, "ReadASICReg failed in %s\n", __func__);
                return false;
            }
            if (regval != 0x8000)
            {
                verbose_printf(LOG_ERROR, ptUserData, "ReadASICReg failed with h6900 = 0x%04x\n", regval);
                return false;
            }
        }
        // Resetting error counters just because??
        if (ResetErrorCounters(ptUserData) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "Reset error counters failed.\n");
            verbose_printf(LOG_ERROR, ptUserData, "  MACIE Error: %s\n", MACIE_Error());
        }
    }
    else // Slow Mode
    {
        unsigned int idle_value = 0;
        unsigned int regtemp = 0;
        unsigned int time_tot = 0;
        unsigned int time_wait = 100;
        // Assume full frame idle time
        unsigned int nout = ASIC_NumOutputs(ptUserData, true);
        unsigned int ff_time_pix = ptUserData->uiDetectorHeight * ptUserData->uiDetectorWidth / nout;
        unsigned int ff_time_ms = ff_time_pix / ptUserData->pixelRate;
        unsigned int timeout = 0;
        unsigned int ypix = 0;
        if ((ypix_burst_stripe(ptUserData, &ypix, false) == true) || (nout > 1))
            timeout = 2 * ff_time_ms;
        else
            timeout = 2 * exposure_frametime_ms(ptUserData);
        // unsigned int timeout = 2 * exposure_frametime_ms(ptUserData);
        if (timeout < time_wait)
            timeout = 2 * time_wait;

        // Write h6900 = 0x8002 to reconfigure ASIC
        struct regInfo *regWrite = new regInfo;
        *regWrite = gen_regInfo(0x6900, 0, 15, 0x8002);
        idle_value = 0x8000;

        // Perfom ASIC write to reconfigure
        if (WriteASICBits(ptUserData, regWrite) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "WriteASICReg failed in %s\n", __func__);
            return false;
        }

        // Poll the ASIC register every 100 msec.
        // Waiting for it to change.
        regtemp = regWrite->value;
        while (regtemp == regWrite->value)
        {
            if (ptUserData->offline_develop == true)
            {
                regWrite->value = idle_value;
                WriteASICBits(ptUserData, regWrite);
                regWrite->value = regtemp;
            }

            if (time_tot > timeout)
            {
                verbose_printf(LOG_ERROR, ptUserData, "Reconfiguration timed out after %i msec\n", timeout);
                break;
            }

            if (ReadASICBits(ptUserData, regWrite, &regtemp) == false)
            {
                verbose_printf(LOG_ERROR, ptUserData, "ReadASICBits failed in %s\n", __func__);
                return false;
            }

            delay(time_wait);
            time_tot += time_wait;
        }
        // Make sure h6900==0x8000
        if (regtemp != idle_value)
        {
            verbose_printf(LOG_ERROR, ptUserData, "Reconfiguration failed with h%04x<%i:%i> = 0x%04x. Expecting 0x%04x\n",
                           regWrite->addr, regWrite->bit0, regWrite->bit1, regtemp, idle_value);
            return false;
        }

        // Make sure detector information is consistent
        unsigned int uiDetType = 0;
        GetASICParameter(ptUserData, "DetectorType", &uiDetType);
        if (uiDetType == 1)
        {
            ptUserData->uiDetectorWidth = 1024;
            ptUserData->uiDetectorHeight = 1024;
            ptUserData->DetectorType = CAMERA_TYPE_H1RG;
        }
        else if (uiDetType == 2)
        {
            ptUserData->uiDetectorWidth = 2048;
            ptUserData->uiDetectorHeight = 2048;
            ptUserData->DetectorType = CAMERA_TYPE_H2RG;
        }
        else if (uiDetType == 4)
        {
            ptUserData->uiDetectorWidth = 4096;
            ptUserData->uiDetectorHeight = 4096;
            ptUserData->DetectorType = CAMERA_TYPE_H4RG;
        }
        else
        {
            verbose_printf(LOG_ERROR, ptUserData, "DetectorType not recognized.\n");
            return false;
        }
    }

    // Check if STRIPE Mode is enabled
    // We need to update RowsPerFrame since this is not done properly
    if (ASIC_STRIPEMode(ptUserData, false, false))
    {
        unsigned int ypix_sub = exposure_ypix(ptUserData);

        unsigned int ExtraLines = 0;
        GetASICParameter(ptUserData, "ExtraLines", &ExtraLines);
        SetASICParameter(ptUserData, "RowsPerFrame", ypix_sub + ExtraLines + 1);
    }

    // Save settings to ptUserData->RegMap
    if (GetASICSettings(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "  GetASICSettings failed to complete in %s.\n", __func__);
        return false;
    }

    // Save exposure frame and ramp times to ptUserData for use during acquisition
    ptUserData->frametime_ms = exposure_frametime_ms(ptUserData);
    ptUserData->ramptime_ms = exposure_ramptime_ms(ptUserData);

    verbose_printf(LOG_INFO, ptUserData, "Reconfiguration succeeded.\n");
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief GetMemAvailable Linux-specific command to get available RAM (kBytes).
/// \param ptUserData The user-set structure containing all the hardware parameters.
unsigned long GetMemAvailable(MACIE_Settings *ptUserData)
{
    string token;
    string linebuffer;
    unsigned long mem = 0;

    std::ifstream infile;

    infile.open("/proc/meminfo");
    if (infile.is_open() == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Could not open file /proc/meminfo \n");
        return 0;
    }
    else
    {
        while (infile >> token)
        {
            if (token == "MemAvailable:")
            {
                if (infile >> mem)
                {
                    verbose_printf(LOG_DEBUG, ptUserData, "MemAvailable = %li kB\n", mem);
                }
                else
                {
                    verbose_printf(LOG_WARNING, ptUserData, "MemAvailable token not found in /proc/meminfo\n");
                    verbose_printf(LOG_WARNING, ptUserData, "MemAvailable set to 0 kB!\n");
                }
            }
        }
        infile.close();
    }

    return mem;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief CalcBuffSize Calculate the size in pixels of a single buffer.
/// \param ptUserData The user-set structure containing all the hardware parameters.
unsigned long CalcBuffSize(MACIE_Settings *ptUserData)
{
    // Updated on 2/16/2021 to always use MACIE_ReadUSBFrameData()
    return CalcBuffSize(ptUserData, 1);
}
////////////////////////////////////////////////////////////////////////////////
/// \brief CalcBuffSize Calculate the size in pixels of a single buffer.
/// \param ptUserData The user-set structure containing all the hardware parameters.
/// \param mode Mode=1: force MACIE_ReadUSBFrameData();
///  Mode=2: MACIE_ReadUSBScienceData().
///  Mode=0: (or otherwise), autoselect based on full frame or subarray setting.
unsigned long CalcBuffSize(MACIE_Settings *ptUserData, unsigned int mode)
{
    // Number of pixels requested in frame
    unsigned long xpix = (unsigned long)exposure_xpix(ptUserData);
    unsigned long ypix = (unsigned long)exposure_ypix(ptUserData);
    unsigned long framesize = xpix * ypix;

    // Size of a full frame
    unsigned long fullframe = (unsigned long)(ptUserData->uiDetectorHeight * ptUserData->uiDetectorWidth);

    // Number of frames in the exposure and in a ramp
    unsigned long nframes_tot = (unsigned long)exposure_nframes(ptUserData, false);
    unsigned long nframes_ramp = nframes_tot / ((unsigned long)ASIC_NRamps(ptUserData, false, 0));

    // Number of pixels in an exposure and ramp
    // unsigned long npix_tot  = nframes_tot * framesize;
    unsigned long npix_ramp = nframes_ramp * framesize;

    unsigned long res = 0;

    // Auto-select Sci or Frame data func
    // Check if acquiring full frame images or subarray
    if ((mode != 1) && (mode != 2))
        mode = (framesize == fullframe) ? 1 : 2;

    if (mode == 1) // Want to use frame function, MACIE_ReadUSBFrameData()
    {
        ptUserData->bUseSciDataFunc = false;
        // Each buffer is the size of a frame
        res = framesize;
    }

    else if (mode == 2) // Otherwise use MACIE_ReadUSBScienceData()
    {
        ptUserData->bUseSciDataFunc = true;
        // Set individual buffer to number of pixels in a ramp
        res = npix_ramp;

        // Enforce res to be an integer multiple of 1024*1024
        unsigned long mult = 1024 * 1024;
        unsigned long res_mod = res % mult;
        if (res_mod != 0)
            res += (mult - res_mod);
    }

    verbose_printf(LOG_INFO, ptUserData, "%s(): Buffer size equals %li pixels (%li bytes)\n", __func__, res, 2 * res);
    return res;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief CalcBuffSize Calculate the number of frame buffers based on user settings.
/// \param ptUserData The user-set structure containing all the hardware parameters.
short CalcNBuffers(MACIE_Settings *ptUserData)
{

    unsigned long res = 1;

    // Number of pixels requested in frame
    unsigned long xpix = (unsigned long)exposure_xpix(ptUserData);
    unsigned long ypix = (unsigned long)exposure_ypix(ptUserData);
    unsigned long framesize = xpix * ypix;

    // Number of frames in the exposure and in a ramp
    unsigned long nframes_tot = (unsigned long)exposure_nframes(ptUserData, false);
    // unsigned long nframes_ramp = nframes_tot / ( (unsigned long) ASIC_NRamps(ptUserData, false, 0) );

    // Number of pixels in an exposure and ramp
    unsigned long npix_tot = nframes_tot * framesize;
    // unsigned long npix_ramp = nframes_ramp * framesize;

    // Minimum and Maximum number of frame buffers allowed to meet requirements
    unsigned long nbuff_min = ptUserData->nPixBuffMin / ptUserData->nPixBuffer + 1;
    unsigned long nbuff_max = ptUserData->nPixBuffMax / ptUserData->nPixBuffer;
    if (nbuff_min < 10)
        nbuff_min = 10;

    // First check that ptUserData->nPixBuffer is valid
    if ((ptUserData->nPixBuffer == 0) || (ptUserData->nPixBuffer > ptUserData->nPixBuffMax))
    {
        verbose_printf(LOG_WARNING, ptUserData, "%s(): Buffer size (%li pixels) is invalid.\n",
                       __func__, ptUserData->nPixBuffer);
        ptUserData->nPixBuffer = CalcBuffSize(ptUserData);
        verbose_printf(LOG_WARNING, ptUserData, "%s(): Updated buffer size: %li pixels (%li MBytes).\n",
                       __func__, ptUserData->nPixBuffer, 2 * ptUserData->nPixBuffer / (1024 * 1024));
    }

    // If we're using MACIE_ReadUSBScienceData(), then make one large buffer,
    // otherwise determine necessary number of buffers to house all requested data
    if (ptUserData->bUseSciDataFunc == true)
    {

        // If npix_tot is less than nPixBuffMin, then set nbuff_min
        if (npix_tot < ptUserData->nPixBuffMin)
            res = nbuff_min;
        else
            res = npix_tot / ptUserData->nPixBuffer + 1;

        // Make sure we're not allocating too few buffers
        if (res < nbuff_min)
            res = nbuff_min;

        // Make sure we're not allocating more buffers than allowed
        if (res > nbuff_max)
            res = nbuff_max;
    }
    else
    {

        // Set to nframes_min if too few frames allocated,
        // otherwise set to total number of requested frames for d/l
        if (nframes_tot < nbuff_min)
            res = nbuff_min;
        else
            res = nframes_tot;

        // Make sure we're not allocating more frames than allowed
        if (res > nbuff_max)
            res = nbuff_max;
    }

    verbose_printf(LOG_INFO, ptUserData, "%s(): nBuffers = %li \n", __func__, res);
    return (short)res;
}

// Calculate buffer size and number of required buffers
void ConfigBuffers(MACIE_Settings *ptUserData)
{
    ptUserData->nPixBuffer = CalcBuffSize(ptUserData);
    ptUserData->nBuffer = CalcNBuffers(ptUserData);
}

// Set size of buffer in pixels. If nPixBuffer is 0, then call CalcBuffSize()
void SetBuffSize(MACIE_Settings *ptUserData, unsigned int nPixBuffer)
{

    if ((nPixBuffer == 0) || (nPixBuffer > ptUserData->nPixBuffMax))
    {
        verbose_printf(LOG_WARNING, ptUserData, "%s(): Buffer size (%li pixels) is invalid.\n",
                       __func__, ptUserData->nPixBuffer);
        ptUserData->nPixBuffer = CalcBuffSize(ptUserData);
    }
    else
    {
        ptUserData->nPixBuffer = nPixBuffer;
    }
}

// Set number of image buffers allocated to receive science data
// If nBuffer set to 0 or <1, then calls CalcNBuffers()
void SetNBuffer(MACIE_Settings *ptUserData, short nBuffer)
{
    if (nBuffer < 1)
    {
        short val = CalcNBuffers(ptUserData);
        verbose_printf(LOG_WARNING, ptUserData, "%s(): nBuffer must be greater than 0. Setting to %i.\n",
                       __func__, val);
        ptUserData->nBuffer = val;
        verbose_printf(LOG_WARNING, ptUserData, "%s(): Updated buffer size: %li pixels (%li MBytes).\n",
                       __func__, ptUserData->nPixBuffer, 2 * ptUserData->nPixBuffer / (1024 * 1024));
    }
    else
    {
        ptUserData->nBuffer = nBuffer;
    }
}

// Determine if subarray size is a valid setting.
// MACIE data management has some bugs that restrict
// certain subarray sizes. This may have been fixed in
// MACIE v5.0 while using frame-by-frame data download.
bool verify_subarray_size(MACIE_Settings *ptUserData, uint nx, uint ny, unsigned long nybtes_ramp)
{

    // If nx is a factor of 512 then requested bytes need to be a multiple of 1048576
    unsigned int nx_remain = nx % 512;
    unsigned long nb_remain = nybtes_ramp % 1048576;
    if ((nx_remain == 0) && (nb_remain != 0))
    {
        if (nb_remain != 0)
        {
            verbose_printf(LOG_WARNING, ptUserData,
                           "Number of requested bytes in a ramp (%li bytes) is not a multiple of 1Mbyte.\n",
                           nybtes_ramp);
        }
        // Check if ny is a power of two
        if ((ny & (ny - 1)) != 0)
        {
            verbose_printf(LOG_WARNING, ptUserData,
                           "For nx=%i, ny may need to be a power of 2 (currently, ny=%i).\n",
                           nx, ny);

            // Warn about the top/bottom reference rows for burst stripe
            uint ypix_temp = 0;
            if (ypix_burst_stripe(ptUserData, &ypix_temp, false))
            {
                verbose_printf(LOG_WARNING, ptUserData,
                               "  BurstStripe is enabled: Make sure to account for top/bottom reference rows (8 total).\n");
            }
        }
        return false;
    }
    return true;
}

// Check to make sure buffer information makes sense
bool VerifyBuffers(MACIE_Settings *ptUserData)
{
    // Conditions to verify:
    // 0. Check that enough memory is available for allocation
    // 1. Total buffer size needs to be less than nPixBuffMax.
    // 2. Total buffer size needs to be more than nPixBuffMin.
    // 3. nPixBuff should accommodate a full ramp.
    // 4. Single Buffer sizes needs to be less than nPixBuffMax
    // 5. Buffer sizes need to be multiples of 1024x1024 (???)
    // 6. If bUseSciDataFunc=false, buffer size must equal frame size
    // 7. We must command more than nBytesMin worth of data from the camera (???)

    // MUST COMMAND DATA THAT IS MULTIPLE OF 1MB??? DATA PACKETS?

    // Number of pixels in frame
    unsigned long xpix = (unsigned long)exposure_xpix(ptUserData);
    unsigned long ypix = (unsigned long)exposure_ypix(ptUserData);
    unsigned long framesize = xpix * ypix;

    // Number of frames in the exposure and in a ramp
    unsigned long nframes_tot = (unsigned long)exposure_nframes(ptUserData, false);
    unsigned long nframes_ramp = nframes_tot / ((unsigned long)ASIC_NRamps(ptUserData, false, 0));

    // Number of pixels in an exposure and ramp
    unsigned long npix_tot = nframes_tot * framesize;
    unsigned long npix_ramp = nframes_ramp * framesize;

    // Buffer information
    unsigned long nBuffer = (unsigned long)ptUserData->nBuffer;
    unsigned long nPixBuffer = ptUserData->nPixBuffer;
    unsigned long nPixBuffTot = nBuffer * nPixBuffer;

    // Number of total bytes requested from ASIC
    unsigned long nbytes_tot = 2 * npix_tot;
    // Number of bytes requested per ramp
    unsigned long nbytes_ramp = 2 * npix_ramp;

    verbose_printf(LOG_DEBUG, ptUserData, "%s(): framesize   = %li pixels\n", __func__, framesize);
    verbose_printf(LOG_DEBUG, ptUserData, "%s(): npix_ramp   = %li pixels\n", __func__, npix_ramp);
    verbose_printf(LOG_DEBUG, ptUserData, "%s(): npix_exp    = %li pixels\n", __func__, npix_tot);
    verbose_printf(LOG_DEBUG, ptUserData, "%s(): nbytes_ramp = %li bytes\n", __func__, nbytes_ramp);
    verbose_printf(LOG_DEBUG, ptUserData, "%s(): nbytes_exp  = %li bytes\n", __func__, nbytes_tot);
    verbose_printf(LOG_DEBUG, ptUserData, "%s(): Total buffer space = %li bytes \n",
                   __func__, 2 * nPixBuffTot);

    // 0. Check that enough memory is available for allocation
    unsigned long memAvailMBytes = GetMemAvailable(ptUserData) / 1024;
    unsigned long memReqMBytes = 2 * nPixBuffTot / (1024 * 1024);
    verbose_printf(LOG_DEBUG, ptUserData, "%s(): Memory Available = %li MBytes\n", __func__, memAvailMBytes);
    verbose_printf(LOG_DEBUG, ptUserData, "%s(): Memory Requested = %li MBytes\n", __func__, memReqMBytes);
    if ((9 * memAvailMBytes) / 10 < memReqMBytes)
    {
        verbose_printf(LOG_WARNING, ptUserData, "%s(): MemAvailable (x0.9) = %li MBytes; Requested = %li MBytes\n",
                       __func__, (9 * memAvailMBytes) / 10, memReqMBytes);
    }
    if (memAvailMBytes < memReqMBytes)
    {
        verbose_printf(LOG_ERROR, ptUserData, "%s(): MemAvailable = %li MBytes; Requested = %li MBytes\n",
                       __func__, memAvailMBytes, memReqMBytes);
        return false;
    }
    // 1. Total buffer size relative to maximum allowed allocation
    if (memReqMBytes > ptUserData->nBytesMax)
    {
        verbose_printf(LOG_ERROR, ptUserData, "%s(): nPixBuffTot = %li. Must be <= %li pixels (ptUserData->nBytesMax / 2)\n",
                       __func__, nPixBuffTot, ptUserData->nBytesMax / 2);
        return false;
    }
    // 2. Total buffer size relative to nPixBuffMin
    if (nPixBuffTot < ptUserData->nPixBuffMin)
    {
        verbose_printf(LOG_ERROR, ptUserData, "%s(): nPixBuffTot = %li. Must be >= %li pixels (nPixBuffMin)\n",
                       __func__, nPixBuffTot, ptUserData->nPixBuffMin);
        return false;
    }
    // 3. nPixBuffTot should accommodate a full ramp for SciData function.
    if ((nPixBuffTot < npix_ramp) && (ptUserData->bUseSciDataFunc == true))
    {
        verbose_printf(LOG_ERROR, ptUserData, "%s(): nPixBuffTot = %li. Must be >= %li pixels (npix_ramp)\n",
                       __func__, nPixBuffTot, npix_ramp);
        return false;
    }

    // 4. Single Buffer sizes needs to be less than nPixBuffMax
    if (nPixBuffer > ptUserData->nPixBuffMax)
    {
        verbose_printf(LOG_ERROR, ptUserData, "%s(): nPixBuffer = %li. Must be <= %li pixels (ptUserData->nPixBuffMax)\n",
                       __func__, nPixBuffer, ptUserData->nPixBuffMax);
        return false;
    }
    // 5. Single Buffer sizes needs to be multiple of 1024x1024
    // if (nPixBuffer % (1024*1024) != 0)
    // {
    //     verbose_printf(LOG_ERROR, ptUserData, "%s(): nPixBuffer = %li; must be multiple of %i\n",
    //                 __func__, nPixBuffer, 1024*1024);
    //     return false;
    // }

    // 6. If bUseSciDataFunc=false, buffer size must equal frame size
    if ((ptUserData->bUseSciDataFunc == false) && (nPixBuffer != framesize))
    {
        verbose_printf(LOG_ERROR, ptUserData, "%s(): nPixBuffer (%li) must equal framesize (%li)\n",
                       __func__, nPixBuffer, framesize);
        return false;
    }
    // 7. We must command more than nBytesMin worth of data from the camera
    // if (nbytes_tot < ptUserData->nBytesMin)
    // {
    //     verbose_printf(LOG_WARNING, ptUserData, "%s(): Total requested bytes (%li) must be >%li (?)\n",
    //                 __func__, nbytes_tot, ptUserData->nBytesMin);
    // }

    // 7. Check subarray size setting
    // TODO: This is temporary until MACIE data handling issue is resolved
    if (verify_subarray_size(ptUserData, xpix, ypix, nbytes_ramp) == false)
    {
        verbose_printf(LOG_WARNING, ptUserData,
                       "%s(): Possible problematic subarray size (nx=%i, ny=%i) with %li bytes in ramp\n",
                       __func__, xpix, ypix, nbytes_ramp);
        // return false;
    }

    verbose_printf(LOG_INFO, ptUserData, "%s(): Buffer info looks good!\n", __func__);
    return true;
}

// Fraction of buffer space currently used
// This can only be called after calling
// MACIE_ConfigureUSBScienceInterface() and before CloseUSBScienceInterface()
double MemBufferFrac(MACIE_Settings *ptUserData)
{
    // int xpix = (int) exposure_xpix(ptUserData);
    // int ypix = (int) exposure_ypix(ptUserData);
    double nbytes_buf = (double)2 * ptUserData->nPixBuffer * ptUserData->nBuffer;
    return ((double)MACIE_AvailableScienceData(ptUserData->handle)) / nbytes_buf;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief AcquireDataUSB Trigger the ASIC to start acquiring data.
///  First configure science USB data interface then trigger exposure acquisition.
/// \param ptUserData The user-set structure containing all the hardware parameters.
/// \param externalTrigger Boolean to indicaton communication and synchronization
///  with an external trigger, such as an external shutter or modulator.
bool AcquireDataUSB(MACIE_Settings *ptUserData, bool externalTrigger)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (ptUserData->connection != MACIE_USB)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Connection type is not USB.\n");
        return false;
    }

    unsigned long handle = ptUserData->handle;
    unsigned char slctMACIEs = ptUserData->slctMACIEs;

    unsigned short data_mode = (ptUserData->DetectorMode == CAMERA_MODE_SLOW) ? 0 : 3;

    // Number of frame buffers to allocate for storing data.
    // short nframes_tot = (short) exposure_nframes(ptUserData, false);
    // short nbuf = (nframes_tot < ptUserData->nBuffer) ? nframes_tot : ptUserData->nBuffer;
    // ptUserData->nBuffer = CalcNBuffers(ptUserData);

    ConfigBuffers(ptUserData);
    // SetBuffSize(ptUserData, exposure_xpix(ptUserData)*exposure_ypix(ptUserData));
    // SetNBuffer(ptUserData, 100);
    // ptUserData->bUseSciDataFunc = false;

    if (VerifyBuffers(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "VerifyBuffers failed in %s\n", __func__);
        return false;
    }
    short nbuf = ptUserData->nBuffer;
    int buffsize = (int)ptUserData->nPixBuffer;

    // short nframes_tot = (short) exposure_nframes(ptUserData, false);
    // short nbuf = 20; //(nframes_tot < ptUserData->nBuffer) ? nframes_tot : ptUserData->nBuffer;
    // int buffsize = exposure_xpix(ptUserData) * exposure_ypix(ptUserData);
    // ptUserData->bUseSciDataFunc = false;

    // Function to update any burst-stripe features (h4300-h4304 and h4034)
    unsigned int ypix = ptUserData->uiDetectorHeight;
    if (ypix_burst_stripe(ptUserData, &ypix, true) == true)
    {
        verbose_printf(LOG_DEBUG, ptUserData, "Burst stripe is enabled with %i rows.\n", ypix);
        // Delay partial frame time to ensure proper transition from full frame to stripe
        delay(int(0.5 * ptUserData->frametime_ms));
    }
    else
    {
        verbose_printf(LOG_DEBUG, ptUserData, "Burst stripe disabled; %i rows.\n", ypix);
    }

    // Make sure h6900<0> is 0 before triggering acquisition.
    // For USB, this must be done before configuring interface,
    // because USB interface's data read and command read share
    // the same USB pipe.
    if (ptUserData->offline_develop == false)
    {
        unsigned int regval = 0;

        regInfo regComp = gen_regInfo(0x6900, 0, 5, 0);
        if (ReadASICBits(ptUserData, &regComp, &regval) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "ReadASICBits failed in %s\n", __func__);
            return false;
        }
        if (regval != 0)
        {
            verbose_printf(LOG_ERROR, ptUserData, "ReadASICBits failed with h6900<5:0> = 0x%04x\n", regval);
            return false;
        }
    }
    verbose_printf(LOG_INFO, ptUserData, "ReadASICBits 0x6900 succeeded.\n");

    // Set up USB3 science data interface for image acquisition.
    // MACIE_CloseUSBScienceInterface needs to be called before we
    // can use any read functions again (e.g., MACIE_ReadASICReg).
    verbose_printf(LOG_INFO, ptUserData, "Configuring science interface...\n");
    verbose_printf(LOG_INFO, ptUserData, "  nbuf = %i\n", nbuf);
    verbose_printf(LOG_INFO, ptUserData, "  buffsize = %i pixels\n", buffsize);
    if (ptUserData->offline_develop == false)
    {
        // Give a slight delay before opening USB interface
        delay(100);
        try
        {
            if (MACIE_ConfigureUSBScienceInterface(handle, slctMACIEs, data_mode, buffsize, nbuf) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData, "Science interface configuration failed.\n");
                return false;
            }
        }
        catch (const std::exception &e)
        {
            verbose_printf(LOG_ERROR, ptUserData,
                           "Caught exception at %s during MACIE_ConfigureUSBScienceInterface().\n",
                           __func__);
            std::cerr << e.what() << '\n';

            return false;
        }
    }
    verbose_printf(LOG_INFO, ptUserData, "Science interface configuration succeeded.\n");
    verbose_printf(LOG_INFO, ptUserData, "Trigger image acquisition...\n");

    // Trigger image acquisition
    if (ptUserData->offline_develop == false)
    {

        // External trigger
        if (externalTrigger)
        {
            // TODO: Experimental
            unsigned int val = 0x8001;
            bool bLineBoundar = true, bFrameBoundary = false;
            if (bLineBoundar)
                val |= 0x0002;
            if (bFrameBoundary)
                val |= 0x0004;

            if (MACIE_WriteMACIEReg(handle, slctMACIEs, 0x01f0, 1) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData,
                               "Writing MACIE 0x01f0 with value 1 failed\n");
                CloseUSBScienceInterface(ptUserData);
                return false;
            }
            if (MACIE_WriteMACIEReg(handle, slctMACIEs, 0x01f1, 0x6900) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData,
                               "Writing ASIC register address 0x6900 to MACIE 0x01f1 failed\n");
                CloseUSBScienceInterface(ptUserData);
                return false;
            }
            if (MACIE_WriteMACIEReg(handle, slctMACIEs, 0x01f2, val) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData,
                               "Writing MACIE 0x01f2 with value 0x%04x failed\n", val);
                CloseUSBScienceInterface(ptUserData);
                return false;
            }
        }
        else
        {

            // Write h6900 = 0x8001 to start acquisition
            struct regInfo *regWrite = new regInfo;
            *regWrite = gen_regInfo(0x6900, 0, 15, 0x8001);

            if (WriteASICBits(ptUserData, regWrite) == false)
            {
                verbose_printf(LOG_ERROR, ptUserData, "Acquisition triggering failed\n");
                CloseUSBScienceInterface(ptUserData);
                return false;
            }
            verbose_printf(LOG_INFO, ptUserData, "Acquisition triggering succeeded\n");
        }
    }

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief AcquireDataGigE Trigger the ASIC to start acquiring data.
///  First configure science GigE data interface then trigger exposure acquisition.
/// \param ptUserData The user-set structure containing all the hardware parameters.
/// \param externalTrigger Boolean to indicaton communication and synchronization
///  with an external trigger, such as an external shutter or modulator.
bool AcquireDataGigE(MACIE_Settings *ptUserData, bool externalTrigger)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (ptUserData->connection != MACIE_GigE)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Connection type is not GigE.\n");
        return false;
    }

    unsigned long handle = ptUserData->handle;
    unsigned char slctMACIEs = ptUserData->slctMACIEs;

    unsigned short data_mode = (ptUserData->DetectorMode == CAMERA_MODE_SLOW) ? 0 : 3;

    // Number of frame buffers to allocate for storing data.
    // short nframes_tot = (short) exposure_nframes(ptUserData, false);
    // short nbuf = (nframes_tot < ptUserData->nBuffer) ? nframes_tot : ptUserData->nBuffer;
    // ptUserData->nBuffer = CalcNBuffers(ptUserData);

    ConfigBuffers(ptUserData);
    // SetBuffSize(ptUserData, exposure_xpix(ptUserData)*exposure_ypix(ptUserData));
    // SetNBuffer(ptUserData, 100);
    // ptUserData->bUseSciDataFunc = false;

    if (VerifyBuffers(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "VerifyBuffers failed in %s\n", __func__);
        return false;
    }
    short nbuf = ptUserData->nBuffer;
    int buffsize = (int)ptUserData->nPixBuffer;

    // short nframes_tot = (short) exposure_nframes(ptUserData, false);
    // short nbuf = 20; //(nframes_tot < ptUserData->nBuffer) ? nframes_tot : ptUserData->nBuffer;
    // int buffsize = exposure_xpix(ptUserData) * exposure_ypix(ptUserData);
    // ptUserData->bUseSciDataFunc = false;

    // Function to update any burst-stripe features (h4300-h4304 and h4034)
    unsigned int ypix = ptUserData->uiDetectorHeight;
    if (ypix_burst_stripe(ptUserData, &ypix, true) == true)
    {
        verbose_printf(LOG_DEBUG, ptUserData, "Burst stripe is enabled with %i rows.\n", ypix);
        // Delay partial frame time to ensure proper transition from full frame to stripe
        delay(int(0.5 * ptUserData->frametime_ms));
    }
    else
    {
        verbose_printf(LOG_DEBUG, ptUserData, "Burst stripe disabled; %i rows.\n", ypix);
    }

    // Make sure h6900<0> is 0 before triggering acquisition.
    // For USB, this must be done before configuring interface,
    // because USB interface's data read and command read share
    // the same USB pipe.
    if (ptUserData->offline_develop == false)
    {
        unsigned int regval = 0;

        regInfo regComp = gen_regInfo(0x6900, 0, 5, 0);
        if (ReadASICBits(ptUserData, &regComp, &regval) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "ReadASICBits failed in %s\n", __func__);
            return false;
        }
        if (regval != 0)
        {
            verbose_printf(LOG_ERROR, ptUserData, "ReadASICBits failed with h6900<5:0> = 0x%04x\n", regval);
            return false;
        }
    }
    verbose_printf(LOG_INFO, ptUserData, "ReadASICBits 0x6900 succeeded.\n");

    // Set up USB3 science data interface for image acquisition.
    // MACIE_CloseUSBScienceInterface needs to be called before we
    // can use any read functions again (e.g., MACIE_ReadASICReg).
    verbose_printf(LOG_INFO, ptUserData, "Configuring science interface...\n");
    verbose_printf(LOG_INFO, ptUserData, "  nbuf = %i\n", nbuf);
    verbose_printf(LOG_INFO, ptUserData, "  buffsize = %i pixels\n", buffsize);
    if (ptUserData->offline_develop == false)
    {
        // Give a slight delay before opening USB interface
        delay(100);
        try
        {
            int bufferSize;
            int remotePort = 42037; //TODO:verify
            if(MACIE_ConfigureGigeScienceInterface(handle, slctMACIEs, data_mode, buffsize, remotePort, &bufferSize) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData, "Science interface configuration failed.\n");
                return false;
            }
        }
        catch (const std::exception &e)
        {
            verbose_printf(LOG_ERROR, ptUserData,
                           "Caught exception at %s during AcquireDataGigE().\n",
                           __func__);
            std::cerr << e.what() << '\n';

            return false;
        }
    }
    verbose_printf(LOG_INFO, ptUserData, "Science interface configuration succeeded.\n");
    verbose_printf(LOG_INFO, ptUserData, "Trigger image acquisition...\n");

    // Trigger image acquisition
    if (ptUserData->offline_develop == false)
    {

        // External trigger
        if (externalTrigger)
        {
            // TODO: Experimental
            unsigned int val = 0x8001;
            bool bLineBoundar = true, bFrameBoundary = false;
            if (bLineBoundar)
                val |= 0x0002;
            if (bFrameBoundary)
                val |= 0x0004;

            if (MACIE_WriteMACIEReg(handle, slctMACIEs, 0x01f0, 1) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData,
                               "Writing MACIE 0x01f0 with value 1 failed\n");
                CloseGigEScienceInterface(ptUserData);
                return false;
            }
            if (MACIE_WriteMACIEReg(handle, slctMACIEs, 0x01f1, 0x6900) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData,
                               "Writing ASIC register address 0x6900 to MACIE 0x01f1 failed\n");
                CloseGigEScienceInterface(ptUserData);
                return false;
            }
            if (MACIE_WriteMACIEReg(handle, slctMACIEs, 0x01f2, val) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData,
                               "Writing MACIE 0x01f2 with value 0x%04x failed\n", val);
                CloseGigEScienceInterface(ptUserData);
                return false;
            }
        }
        else
        {

            // Write h6900 = 0x8001 to start acquisition
            struct regInfo *regWrite = new regInfo;
            *regWrite = gen_regInfo(0x6900, 0, 15, 0x8001);

            if (WriteASICBits(ptUserData, regWrite) == false)
            {
                verbose_printf(LOG_ERROR, ptUserData, "Acquisition triggering failed\n");
                CloseGigEScienceInterface(ptUserData);
                return false;
            }
            verbose_printf(LOG_INFO, ptUserData, "Acquisition triggering succeeded\n");
        }
    }

    return true;
}


unsigned int getFileNumStart(MACIE_Settings *ptUserData)
{

    string strDir = ptUserData->saveDir;

    // Create save directory if it doesn't exist
    struct stat st = {0};
    if (stat(strDir.c_str(), &st) == -1)
        mkdir(strDir.c_str(), 0700);

    // Go through files in save directory to find last written file number
    DIR *dir = opendir(strDir.c_str());
    struct dirent *ent;
    uint val;
    uint max_val = 0;
    int pos;
    string s, sub;
    while ((ent = readdir(dir)) != NULL)
    {
        s = string(ent->d_name);
        if ((s.rfind(".fits") != string::npos) && (s.size() > 6))
        {
            pos = s.rfind("_");
            sub = s.substr(pos + 1, 6);
            val = atoi(sub.c_str());
            if (val >= max_val)
                max_val = val + 1;
        }
    }
    closedir(dir);
    return max_val;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief getFileNames Return a string vector of filenames.
/// \param ptUserData The user-set structure containing the hardware parameters
std::vector<std::string> getFileNames(MACIE_Settings *ptUserData)
{
    uint nfiles = ptUserData->uiNumSaves;
    string strDir = ptUserData->saveDir;
    string strPre = ptUserData->filePrefix;
    uint fnum = getFileNumStart(ptUserData);

    std::stringstream ss;

    string name = "";
    std::vector<std::string> names; // Empty on creation
    // printf("nfiles: %i\n", nfiles);
    for (uint i = 0; i < nfiles; ++i)
    {
        ss.str("");
        ss << std::setw(6) << std::setfill('0') << fnum;
        name = strDir + strPre + ss.str() + ".fits";
        names.push_back(name);
        // verbose_printf(LOG_INFO, ptUserData, " filename: %s\n", names[i].c_str());
        fnum++;
    }
    return names;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief CloseUSBScienceInterface Close MACIE USB Science interface.
///  Normally this function should be called after the image acquisition is done.
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool CloseUSBScienceInterface(MACIE_Settings *ptUserData)
{
    verbose_printf(LOG_INFO, ptUserData, "Closing MACIE USB science interface...\n");
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_CloseUSBScienceInterface(ptUserData->handle, ptUserData->slctMACIEs) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_CloseUSBScienceInterface failed: %s\n", MACIE_Error());
            return false;
        }
    }
    // Set burst stripe to idle in full frame
    burst_stripe_set_ffidle(ptUserData);

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief CloseGigEScienceInterface Close MACIE GigE Science interface.
///  Normally this function should be called after the image acquisition is done.
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool CloseGigEScienceInterface(MACIE_Settings *ptUserData)
{
    verbose_printf(LOG_INFO, ptUserData, "Closing MACIE GigE science interface...\n");
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_CloseGigeScienceInterface(ptUserData->handle, ptUserData->slctMACIEs) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_CloseGigeScienceInterface failed: %s\n", MACIE_Error());
            return false;
        }
    }
    // Set burst stripe to idle in full frame
    burst_stripe_set_ffidle(ptUserData);

    return true;
}

void HaltCameraAcq(MACIE_Settings *ptUserData)
{
    verbose_printf(LOG_INFO, ptUserData, "Halting data acquisition...\n");
    // verbose_printf(LOG_INFO, ptUserData, "Waiting for last ramp to complete...\n");

    if (ptUserData->DetectorMode == CAMERA_MODE_FAST)
    {
        WriteASICReg(ptUserData, 0x6900, 0x8000);
        delay(100);
    }
    else
    {
        WriteASICReg(ptUserData, 0x6900, 0x8000);
        // TODO: Is this delay necessary? Frame boundary?
        // int tframe_ms = (int)exposure_frametime_ms(ptUserData);
        // delay(tframe_ms);
        delay(100);
    }
}

////////////////////////////////////////////////////////////////////////////////
/// \brief DownloadAndSaveAllUSB Function to download all requested frames
///  from MACIE, coadd average if requested, and save to FITS.
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool DownloadAndSaveAllUSB(MACIE_Settings *ptUserData)
{
    // Number of ramps to coadd together
    const int ncoadds = (int)ptUserData->uiNumCoadds;

    const int xpix = (int)exposure_xpix(ptUserData);
    const int ypix = (int)exposure_ypix(ptUserData);
    // Number of pixels in frame for download
    const int framesize = xpix * ypix;

    // Number of requested ramps
    const int nramps = (int)ASIC_NRamps(ptUserData, false, 0);
    // Number of groups in a ramp
    const int ngroups = (int)ASIC_NGroups(ptUserData, false, 0);
    // Number of frame reads in a group
    const int nreads = (int)ASIC_NReads(ptUserData, false, 0);

    // Saving reset frames?
    int nresets_ramp = (int)ASIC_NResets(ptUserData, false, 0);
    int nresets_save = 0;
    unsigned int val = 0;
    if (GetASICParameter(ptUserData, "SaveRstFrames", &val) == true)
        if (val == 1)
            nresets_save = nresets_ramp;

    // Number of frames in a ramp (to download)
    const int nframes_ramp = ngroups * nreads + nresets_save;
    // Number of pixels in ramp (to download)
    const int rampsize = framesize * nframes_ramp;

    // clock_t t, t0;
    timestamp_t t, t0;
    double time_taken;

    // Set up data axes information
    std::vector<string> filenames = getFileNames(ptUserData);
    vector<long> naxis;
    naxis.push_back(xpix);
    naxis.push_back(ypix);
    if (nframes_ramp > 1)
        naxis.push_back(nframes_ramp);

    // Frame and Ramp times
    double frametime_ms = ptUserData->frametime_ms;
    double ramptime_ms = ptUserData->ramptime_ms;
    // Calculate a timeout to wait for data.
    // Assume full frame idle time
    // Timeout setting while waiting for data download to trigger
    int triggerTimeout = int(ramptime_ms + 2 * frametime_ms + 100);
    // unsigned int nout = ASIC_NumOutputs(ptUserData, true);
    // unsigned int ff_time_pix = ptUserData->uiDetectorHeight * ptUserData->uiDetectorWidth / nout;
    // double ff_time_ms  = (double) ff_time_pix / ptUserData->pixelRate;
    // int triggerTimeout = int(exposure_nframes(ptUserData, true) + 2) * int(ff_time_ms);
    // Wait delta (in msec) to sample available science data bytes
    int wait_delta = int(frametime_ms / 10);
    if (wait_delta < 1)
        wait_delta = 1;

    // Allocate memory to store each ramp
    unsigned short *pData;
    try
    {
        // long SIZE = (long) rampsize;
        pData = new unsigned short[rampsize]();
    }
    catch (const std::exception &e)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Failed to allocate memory for pData at %s.\n", __func__);
        std::cerr << e.what() << '\n';

        // Explicitly send Halt command (h6900=0x8000)
        HaltCameraAcq(ptUserData);
        CloseGigEScienceInterface(ptUserData);

        return false;
    }
    // 32-bit coadd buffer (actually takes average of ramps)
    float *pRampBuffer;
    try
    {
        pRampBuffer = new float[rampsize]();
    }
    catch (const std::exception &e)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Failed to allocate memory for pRampBuffer at %s.\n", __func__);
        std::cerr << e.what() << '\n';

        // Delete all data
        delete[] pData;

        // Explicitly send Halt command (h6900=0x8000)
        HaltCameraAcq(ptUserData);
        CloseGigEScienceInterface(ptUserData);

        return false;
    }

    int coadd_cnt = 0;
    int ifile = 0;

    // Flag indicating buffer is getting too full
    bool buff_flag = false;
    double buff_frac = 0;
    uint nbytes_req = uint(rampsize) * uint(nramps);

    t0 = get_timestamp();
    for (int ii = 0; ii < nramps; ++ii)
    {

        // Testing of Halt Acquisition
        // if (ii==30)
        // {
        //     verbose_printf(LOG_ERROR, ptUserData, "Halt encountered on ramp %i of %i.\n", ii+1, nramps);
        //     break;
        // }

        // If the memory buffer is 90% full, then set buffer overflow flag.
        // But only if the number of requested bytes is greater than max buffer size.
        // Resume when we've gone below 65%
        buff_frac = MemBufferFrac(ptUserData);
        verbose_printf(LOG_INFO, ptUserData, "  Buffer fraction: %f\n", buff_frac);
        if ((buff_frac > 0.9) && (nbytes_req > 2 * ptUserData->nPixBuffer))
            buff_flag = true;
        if (buff_flag && (buff_frac < 0.65))
            buff_flag = false;

        // Download data as it becomes available
        t = get_timestamp();
        if (DownloadRampUSB(ptUserData, pData, framesize, nframes_ramp, triggerTimeout, wait_delta) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "Failed download on ramp %i of %i.\n", ii + 1, nramps);
            verbose_printf(LOG_ERROR, ptUserData, "Breaking out of acquisition on sequence %i of %i.\n", ii + 1, nramps);
            break;
        }
        t = get_timestamp() - t;
        time_taken = t / 1000000.0L;
        verbose_printf(LOG_INFO, ptUserData, "  DownloadRampUSB total time: %f seconds\n", time_taken);

        // Go to next iteration if memory buffer is too full
        if (buff_flag)
        {
            verbose_printf(LOG_WARNING, ptUserData, "  Buffer reaching max capacity. Skipping ramp %i of %i.\n", ii + 1, nramps);
            continue;
        }

        // If no coadding, keep in 16-bit format and save
        if (ncoadds == 1)
        {
            if (ptUserData->bSaveData)
            {
                verbose_printf(LOG_INFO, ptUserData, "Writing: %s\n", filenames[ifile].c_str());
                t = get_timestamp();
                if (WriteFITSRamp(pData, naxis, USHORT_IMG, filenames[ifile]) == false)
                {
                    verbose_printf(LOG_ERROR, ptUserData, "Failed to write FITS (16-bit) at %s\n", __func__);
                    verbose_printf(LOG_ERROR, ptUserData, "Breaking out of acquisition on sequence %i of %i.\n", ii + 1, nramps);
                    break;
                }
                t = get_timestamp() - t;
                time_taken = t / 1000000.0L;
                verbose_printf(LOG_INFO, ptUserData, "  Time to write FITS file: %f seconds\n\n", time_taken);
                // Increment file name index
                ifile++;
            }
        }
        // Otherwise add pData to 32-bit coadder
        else
        {
            // Pixel-by-pixel add to buffer
            t = get_timestamp();
            for (int jj = 0; jj < rampsize; ++jj)
                pRampBuffer[jj] += pData[jj];
            t = get_timestamp() - t;
            time_taken = t / 1000000.0L;
            verbose_printf(LOG_INFO, ptUserData, "  Time to take copy ramp: %f seconds\n", time_taken);

            // Increment coadd counter
            coadd_cnt++;

            if (coadd_cnt == ncoadds)
            {
                // Take average
                if (ncoadds > 1)
                {
                    t = get_timestamp();
                    for (int jj = 0; jj < rampsize; ++jj)
                        pRampBuffer[jj] /= ncoadds;
                    t = get_timestamp() - t;
                    time_taken = t / 1000000.0L;
                    verbose_printf(LOG_INFO, ptUserData, "  Time to take average: %f seconds\n", time_taken);
                }

                if (ptUserData->bSaveData)
                {
                    // Save FITS files
                    verbose_printf(LOG_INFO, ptUserData, "Writing: %s\n", filenames[ifile].c_str());
                    t = get_timestamp();
                    if (WriteFITSRamp(pRampBuffer, naxis, FLOAT_IMG, filenames[ifile]) == false)
                    {
                        verbose_printf(LOG_ERROR, ptUserData, "Failed to write FITS (32-bit) at %s\n", __func__);
                        verbose_printf(LOG_ERROR, ptUserData, "Breaking out of acquisition on sequence %i of %i.\n", ii + 1, nramps);
                        break;
                    }
                    t = get_timestamp() - t;
                    time_taken = t / 1000000.0L;
                    verbose_printf(LOG_INFO, ptUserData, "  Time to write FITS file: %f seconds\n\n", time_taken);
                    // Increment file name index
                    ifile++;
                }

                // Reset pRampBuffer to 0s
                memset(pRampBuffer, 0, rampsize * sizeof(pRampBuffer[0]));
                // Clear counter
                coadd_cnt = 0;
            }
        }
    }

    t = get_timestamp() - t0;
    time_taken = t / 1000000.0L;
    verbose_printf(LOG_INFO, ptUserData, "  DownloadAll for loop time: %f seconds\n\n", time_taken);

    // // Test to see if we are getting more bytes than expected
    // if (get_verbose(ptUserData) == LOG_DEBUG)
    // {
    //     long nbytes = 0;
    //     int delay_time = int(ramptime_ms);
    //     int wait_total = 0;
    //     wait_delta = int(frametime_ms / 5);
    //     if (wait_delta < 1)
    //         wait_delta = 1;

    //     verbose_printf(LOG_DEBUG, ptUserData, "Delaying %i ms to see if more bytes come down...\n", delay_time);
    //     // Poll MACIE_AvailableScienceData
    //     while (wait_total < delay_time)
    //     {
    //         nbytes = (long) MACIE_AvailableScienceData(ptUserData->handle);
    //         verbose_printf(LOG_DEBUG, ptUserData, "  wait_total (ms): %i, nbytes: %li\n", wait_total, nbytes);

    //         delay(wait_delta);
    //         wait_total += wait_delta;
    //     }
    //     nbytes = (long) MACIE_AvailableScienceData(ptUserData->handle);
    //     verbose_printf(LOG_DEBUG, ptUserData, "  wait_total (ms): %i, nbytes: %li\n", wait_total, nbytes);

    //     if (nbytes>0)
    //         verbose_printf(LOG_WARNING, ptUserData, "  Additional %li bytes after exposure!\n", nbytes);
    // }

    // Delete all data
    delete[] pData;
    delete[] pRampBuffer;

    // Explicitly send Halt command (h6900=0x8000)
    HaltCameraAcq(ptUserData);
    delay(100);
    if (CloseGigEScienceInterface(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "CloseGigEScienceInterface failed after acquisition\n");
        return false;
    }
    else
        verbose_printf(LOG_INFO, ptUserData, "CloseGigEScienceInterface succeeded after acquisition\n");
    // Do this again??

    return true;
}

//
////////////////////////////////////////////////////////////////////////////////
/// \brief DownloadRampUSB Download a ramp. Choose whether or not to use
///  DownloadRampUSB_Frame or DownloadRampUSB_Data .
/// \param ptUserData     The user-set structure containing all the hardware parameters.
/// \param pData          Pointer to a pre-allocated unsigned short data buffer.
/// \param framesize      Number of pixels in a frame.
/// \param nframes_save   Number of frames read in ramp.
/// \param triggerTimeout How long to wait for frames to complete before failing
///  (e.g. a ramp time)
/// \param wait_delta     Time interval to poll for available bytes
///  (e.g. some fraction of a frame time)
bool DownloadRampUSB(MACIE_Settings *ptUserData, unsigned short pData[], long framesize,
                     long nframes_save, int triggerTimeout, int wait_delta)
{

    // Before downloading, make sure to clear all data in ramp mem storage
    // This helps identify missing data in saved frames due to d/l errors.
    uint rampsize = (uint)framesize * nframes_save;
    memset(pData, 0, rampsize * sizeof(pData[0]));

    // Select which download function to use (Data vs Frame) based on user setting.
    // Generally, these correspond to subbarray (USB_Data) and full frame (USB_Frame).
    if (ptUserData->bUseSciDataFunc == true)
    {
        return DownloadRampUSB_Data(ptUserData, pData, framesize, nframes_save, triggerTimeout, wait_delta);
    }
    else
    {
        return DownloadRampUSB_Frame(ptUserData, pData, framesize, nframes_save, triggerTimeout, wait_delta);
    }
}

////////////////////////////////////////////////////////////////////////////////
/// \brief DownloadRampUSB_Frame Download a ramp frame-by-frame. First, we check
///  how many bytes are available on the MACIE buffer. Once a frame's worth
///  of data exists, it downloads and saves those bytes into the approrpriate
///  location in pData. Continue for the next frame until ramp is completed.
bool DownloadRampUSB_Frame(MACIE_Settings *ptUserData, unsigned short pData[], long framesize,
                           long nframes_save, int triggerTimeout, int wait_delta)
{

    long nbytes = 0;
    long nbytes_frm = framesize * 2; // 16 bits = 2 bytes

    verbose_printf(LOG_DEBUG, ptUserData, "triggerTimeout = %i, wait_delta:%i\n", triggerTimeout, wait_delta);
    // unsigned short dltimeout = (ptUserData->DetectorMode==CAMERA_MODE_SLOW) ? 6500 : 1500;
    int wait_total = 0;

    // Delay the larger of 1 second or 1 frame time to see if rest comes down
    int delay_time = 1000;
    int frame_time_ms = (int)ptUserData->frametime_ms;
    if (delay_time < frame_time_ms)
        delay_time = frame_time_ms;

    // Download timeout
    unsigned short dltimeout = (ushort)ptUserData->ramptime_ms;

    timestamp_t t;
    double time_taken = 0;
    for (long i = 0; i < nframes_save; ++i)
    {
        verbose_printf(LOG_DEBUG, ptUserData, "  Frame %li of %li\n", i + 1, nframes_save);
        nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);
        wait_total = 0;

        // Poll available science data
        // When any amount of data shows up, break out and call the d/l function
        // Timeout if no data after triggertimout is reached
        while (nbytes <= 0)
        {
            // Delay for some time
            delay(wait_delta);
            wait_total += wait_delta;

            // Check to see if data has shown up on port yet
            if (ptUserData->offline_develop == true)
                nbytes = nbytes_frm;
            else
                nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);

            verbose_printf(LOG_DEBUG, ptUserData, "  wait_total (ms): %i, nbytes: %li\n", wait_total, nbytes);

            // Return false if we've reached time limit but haven't gotten all the bytes
            if (wait_total > triggerTimeout)
            {
                verbose_printf(LOG_ERROR, ptUserData, "Trigger timeout limit of %i ms reached at: %s\n",
                               triggerTimeout, __func__);
                verbose_printf(LOG_ERROR, ptUserData, "  Frame %li of %li.\n", i + 1, nframes_save);
                verbose_printf(LOG_ERROR, ptUserData, "  Expecting %li bytes. Only %li bytes available in %i ms.\n",
                               nbytes_frm, nbytes, wait_total);

                // Delay the larger of 1 second or 1 frame time to see if rest comes down
                verbose_printf(LOG_ERROR, ptUserData, "  Delaying %i msec more...\n", delay_time);
                delay(delay_time);

                nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);
                verbose_printf(LOG_WARNING, ptUserData, "  After delay, nbytes available: %li\n", nbytes);
                if (nbytes < nbytes_frm)
                {
                    verbose_printf(LOG_ERROR, ptUserData, "  Returning...\n");
                    return false;
                }
                else
                {
                    verbose_printf(LOG_ERROR, ptUserData, "  Continuing...\n");
                    break;
                }
            }
        }

        if (get_verbose(ptUserData) == LOG_DEBUG)
        {
            wait_total = 0;
            while (wait_total < delay_time)
            {
                nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);
                verbose_printf(LOG_DEBUG, ptUserData, "  wait_total (ms): %i, nbytes: %li\n", wait_total, nbytes);

                delay(wait_delta);
                wait_total += wait_delta;

                if (nbytes >= nbytes_frm)
                    break;
            }
            nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);
        }
        verbose_printf(LOG_DEBUG, ptUserData, "  wait_total (ms): %i, nbytes: %li\n", wait_total, nbytes);

        // Download a frame into pData buffer
        t = get_timestamp();
        // if (DownloadDataUSB(ptUserData, &pData[i*framesize], framesize, dltimeout)==false)
        if (DownloadFrameUSB(ptUserData, &pData[i * framesize], framesize, dltimeout) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "DownloadFrameUSB failed at %s\n", __func__);
            verbose_printf(LOG_ERROR, ptUserData, "  Frame %li of %li.\n", i + 1, nframes_save);

            verbose_printf(LOG_ERROR, ptUserData, "  Saw nbytes before d/l attempt: %li)\n", nbytes);
            nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);
            verbose_printf(LOG_ERROR, ptUserData, "  Saw nbytes after d/l attempt: %li)\n", nbytes);

            return false;
        }
        t = get_timestamp() - t;
        time_taken = t / 1000.0L;

        verbose_printf(LOG_DEBUG, ptUserData, "  Frame dl time: %.0f ms (wait_total: %i ms, nbytes: %li)\n",
                       time_taken, wait_total, nbytes);
    }
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief DownloadFrameUSB Read a single frame's woth of science data.
/// \param ptUserData The user-set structure containing all the hardware parameters.
/// \param pData Pointer to a pre-allocated unsigned short data buffer.
/// \param SIZE Number of science data words to read (equal to framesize=xpix*ypix).
/// \param timeout Unsigned short (in ms) after which the function will
///  stop reading from the port and return NULL.
bool DownloadFrameUSB(MACIE_Settings *ptUserData, unsigned short pData[], long SIZE, unsigned short timeout)
{

    // unsigned int timeout = (ptUserData->DetectorMode==CAMERA_MODE_SLOW) ? 6500 : 1500;
    if (ptUserData->offline_develop == true)
    {
        // long xpix = (long) exposure_xpix(ptUserData);
        // long ypix = (long) exposure_ypix(ptUserData);
        exposure_test_data(ptUserData, pData, SIZE); // xpix*ypix);
    }
    else
    {
        ushort *ptemp = MACIE_ReadGigeScienceFrame(ptUserData->handle, timeout);
        // Check if returns NULL
        if (!ptemp)
        {
            // Wait 1000 msec and try again
            verbose_printf(LOG_ERROR, ptUserData, "Null frame encountered in function: %s. Waiting 1 sec and re-attempting...\n", __func__);
            verbose_printf(LOG_ERROR, ptUserData, "  MACIE Error string: %s\n", MACIE_Error());
            delay(1000);
            ptemp = MACIE_ReadUSBScienceFrame(ptUserData->handle, timeout);
        }
        // If still NULL, then return false
        if (!ptemp)
        {
            verbose_printf(LOG_ERROR, ptUserData, "Null frame encountered in function: %s\n", __func__);
            verbose_printf(LOG_ERROR, ptUserData, "  MACIE Error string: %s\n", MACIE_Error());
            return false;
        }

        // Fast Mode observations are backwards
        if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
        {
            memcpy(pData, ptemp, sizeof(ushort) * SIZE);
        }
        else
        {
            // for (long i=0; i<SIZE; i++)
            //     pData[i] = 4095 - ptemp[i];
            // Fast Mode even/odd columns are switched
            // Unroll the for loop by do 16 elements at a time
            // Improves overall execution time of this function by 20-30%
            for (long i = 0; i < SIZE; i = i + 16)
            {
                pData[i] = 4095 - ptemp[i + 1];       // Odd into even
                pData[i + 1] = 4095 - ptemp[i];       // Even into odd
                pData[i + 2] = 4095 - ptemp[i + 3];   // Odd into even
                pData[i + 3] = 4095 - ptemp[i + 2];   // Even into odd
                pData[i + 4] = 4095 - ptemp[i + 5];   // Odd into even
                pData[i + 5] = 4095 - ptemp[i + 4];   // Even into odd
                pData[i + 6] = 4095 - ptemp[i + 7];   // Odd into even
                pData[i + 7] = 4095 - ptemp[i + 6];   // Even into odd
                pData[i + 8] = 4095 - ptemp[i + 9];   // Odd into even
                pData[i + 9] = 4095 - ptemp[i + 8];   // Even into odd
                pData[i + 10] = 4095 - ptemp[i + 11]; // Odd into even
                pData[i + 11] = 4095 - ptemp[i + 10]; // Even into odd
                pData[i + 12] = 4095 - ptemp[i + 13]; // Odd into even
                pData[i + 13] = 4095 - ptemp[i + 12]; // Even into odd
                pData[i + 14] = 4095 - ptemp[i + 15]; // Odd into even
                pData[i + 15] = 4095 - ptemp[i + 14]; // Even into odd
            }
        }
    }

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief DownloadRampUSB_Data Same as DownloadRampUSB_Frame, except grabs the
///  entire ramp at once rather than frame by frame. Sometimes, for small
///  subarray (<1Mbytes), MACIE_AvailableScienceData will not report the
///  presence of these bytes, so we must assume they're in the buffer and let
///  MACIE_ReadUSBScienceData take care of it.
bool DownloadRampUSB_Data(MACIE_Settings *ptUserData, unsigned short pData[], long framesize,
                          long nframes_save, int triggerTimeout, int wait_delta)
{

    long nbytes_ramp = nframes_save * framesize * 2; // 16 bits = 2 bytes

    // Download timeout (1.5 times the full ramp time)
    unsigned short dltimeout = (ushort)1.5 * ptUserData->ramptime_ms;
    int wait_total = 0;

    verbose_printf(LOG_DEBUG, ptUserData, "triggerTimeout = %i, wait_delta:%i\n",
                   triggerTimeout, wait_delta);

    timestamp_t t;
    long nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);

    // Poll available science data
    while (nbytes <= 0)
    {
        // Delay for some time
        delay(wait_delta);

        // Check to see if data has shown up on port yet
        if (ptUserData->offline_develop == true)
            nbytes = nbytes_ramp;
        else
            nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);

        wait_total += wait_delta;
        verbose_printf(LOG_DEBUG, ptUserData, "  wait_total (ms): %i, nbytes: %li\n", wait_total, nbytes);

        // Return false if we've reached time limit but haven't gotten all the bytes.
        // There's a special case if nbytes isn't a multiple of 1024x1024, then
        // the remainder bytes don't show up with MACIE_AvailableScienceData(),
        // but we can still download them from the buffer. In this case, assume
        // the bytes are there and just break out. Usually this only occurs on the
        // very first or very last ramp.
        if (wait_total > triggerTimeout)
        {
            verbose_printf(LOG_WARNING, ptUserData, "Trigger timeout limit of %i ms reached at: %s\n",
                           triggerTimeout, __func__);
            if (nbytes_ramp % (1024 * 1024) != 0)
            {
                // delay(100);
                break;
            }

            verbose_printf(LOG_WARNING, ptUserData, "  Expecting %li bytes. %li bytes available in %i ms.\n",
                           nbytes_ramp, nbytes, wait_total);

            // Delay the larger of 1 second to see if rest comes down
            verbose_printf(LOG_ERROR, ptUserData, "  Delaying %i msec more...\n", 1000);
            delay(1000);

            nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);
            verbose_printf(LOG_WARNING, ptUserData, "  After delay, nbytes available: %li\n", nbytes);
            if (nbytes < nbytes_ramp)
            {
                verbose_printf(LOG_ERROR, ptUserData, "  Insufficient number of bytes available...\n");
                return false;
            }
            else
            {
                verbose_printf(LOG_WARNING, ptUserData, "  Continuing...\n");
                break;
            }
        }
    }

    if (get_verbose(ptUserData) == LOG_DEBUG)
    {
        wait_total = 0;
        while (wait_total < int(ptUserData->ramptime_ms))
        {
            nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);
            verbose_printf(LOG_DEBUG, ptUserData, "  wait_total (ms): %i, nbytes: %li\n", wait_total, nbytes);

            delay(wait_delta);
            wait_total += wait_delta;
            if (nbytes >= nbytes_ramp)
                break;
        }
        nbytes = (long)MACIE_AvailableScienceData(ptUserData->handle);
    }
    verbose_printf(LOG_DEBUG, ptUserData, "  wait_total (ms): %i, nbytes: %li\n", wait_total, nbytes);

    // Download a ramp into pData buffer
    t = get_timestamp();
    if (DownloadDataUSB(ptUserData, &pData[0], framesize * nframes_save, dltimeout) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "DownloadDataUSB failed at %s\n", __func__);
        return false;
    }
    t = get_timestamp() - t;
    double time_taken = t / 1000.0L;

    verbose_printf(LOG_DEBUG, ptUserData, "  Ramp dl time: %.0f ms (wait_total: %i ms, nbytes: %li)\n",
                   time_taken, wait_total, nbytes);

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief DownloadDataUSB Read science data. Capture some arbitrary amount of
///  science data.
/// \param ptUserData The user-set structure containing all the hardware parameters.
/// \param pData Pointer to a pre-allocated unsigned short data buffer.
/// \param SIZE Number of science data words to read.
/// \param timeout Unsigned short (in ms) after which the function will
///  stop reading from the port and return NULL.
bool DownloadDataUSB(MACIE_Settings *ptUserData, unsigned short pData[], long SIZE, unsigned short timeout)
{
    int nwords = 0;

    // unsigned int timeout = (ptUserData->DetectorMode==CAMERA_MODE_SLOW) ? 6500 : 1500;
    if (ptUserData->offline_develop == true)
    {
        exposure_test_data(ptUserData, pData, SIZE);
        return true;
    }
    else
    {
        nwords = MACIE_ReadGigeScienceData(ptUserData->handle, timeout, SIZE, pData);
        verbose_printf(LOG_INFO, ptUserData, "  Number of acquired science data words: %i pixels (%i bytes)\n", nwords, 2 * nwords);
    }

    if (!pData)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Null frame: %s\n", MACIE_Error());
        return false;
    }
    else if (ptUserData->DetectorMode == CAMERA_MODE_FAST)
    {
        // for (long i=0; i<SIZE; i++)
        //     pData[i] = 4095 - pData[i];
        // Fast Mode even/odd columns are switched
        unsigned short tmp = 0;
        for (long i = 0; i < SIZE; i = i + 2)
        {
            tmp = 4095 - pData[i];
            pData[i] = 4095 - pData[i + 1]; // Odd into even
            pData[i + 1] = tmp;             // Even into odd
        }
    }

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief WriteFITSRamp Write ramp data to FITS data cube.
/// \param pData Pointer to a data buffer. Type must match bitpix param.
/// \param naxis A vector storing the axis dimensions (NAXIS1, NAXIS2, NAXIS3).
/// \param bitpix Pixel bit information.
/// \param filename String holding the output file path + name.
bool WriteFITSRamp(void *pData, vector<long> naxis, int bitpix, string filename)
{

    long naxes = naxis.size();
    long npix = (naxes == 2) ? naxis[0] * naxis[1] : naxis[0] * naxis[1] * naxis[2];

    // pointer to the FITS file
    fitsfile *poutfits;

    // BITPIX options
    // 1. [U]SHORT_IMG 		(16-bit [un]signed) -> T[U]SHORT			// BITPIX=16
    // 2. [U]LONG_IMG 		(32-bit [un]signed) -> T[U]LONG				// BITPIX=32
    // 3. [U]LONGLONG_IMG (64-bit [un]signed) -> T[U]LONGLONG		// BITPIX=64
    // 4. FLOAT_IMG (32-bit)  -> TFLOAT			// BITPIX=-32
    // 5. DOUBLE_IMG (64-bit)	-> TDOUBLE		// BITPIX=-64

    int datatype;
    switch (bitpix)
    {
    case SHORT_IMG:
        datatype = TSHORT;
        break;
    case USHORT_IMG:
        datatype = TUSHORT;
        break;

    case LONG_IMG:
        datatype = TLONG;
        break;
    case ULONG_IMG:
        datatype = TULONG;
        break;

    case LONGLONG_IMG:
        datatype = TLONGLONG;
        break;
        // case ULONGLONG_IMG: datatype = TULONGLONG;
        // 	break;

    case FLOAT_IMG:
        datatype = TFLOAT;
        break;
    case DOUBLE_IMG:
        datatype = TDOUBLE;
        break;

    default:
        datatype = TUINT;
        break;
    }

    int status = 0;

    // create new FITS file
    if (fits_create_file(&poutfits, filename.c_str(), &status))
    {
        if (status)
        {
            printf("Failed at fits_create_file()\n");
            fits_report_error(stderr, status);
            return false;
        }
    }

    // Write the required keywords for the primary array image
    if (fits_create_img(poutfits, bitpix, naxes, &naxis[0], &status))
    {
        if (status)
        {
            printf("Failed at fits_create_img()\n");
            fits_report_error(stderr, status);
            return false;
        }
    }

    // Write data array to the FITS file
    if (fits_write_img(poutfits, datatype, 1, npix, pData, &status))
    {
        if (status)
        {
            printf("Failed at fits_write_img()\n");
            fits_report_error(stderr, status);
            return false;
        }
    }

    // Add header keywords

    // Close FITS file
    if (fits_close_file(poutfits, &status))
        ;
    {
        if (status)
        {
            printf("Failed at fits_close_file()\n");
            fits_report_error(stderr, status);
            return false;
        }
    }

    return true;
}

// Creates a data of some size to simulate output of MACIE_ReadUSBScienceData.
void exposure_test_data(MACIE_Settings *ptUserData, unsigned short pData[], long SIZE)
{

    long xpix = (long)exposure_xpix(ptUserData);
    unsigned int nout = ASIC_NumOutputs(ptUserData);

    long chsize = xpix / long(nout);

    // Print out expected channel values
    verbose_printf(LOG_INFO, ptUserData, "Fake Data channels values = chnum*100 + %i\n", ptUserData->uiFileNum);

    // srand(time(NULL));
    for (long i = 0; i < SIZE; ++i)
    {
        pData[i] = 100 * int((i % xpix) / chsize + 1) + int(ptUserData->uiFileNum); // + int(rand() % 10);
        // printf("pData[%lu] = %i\n", i, *(pData + i));
    }
    // Every time we call this function, increment uiFileNum to get unique offset
    ptUserData->uiFileNum++;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief GetMACIEClockRate Get the current MACIE master clock rate
///  from the MACIE card. Saves in ptUserData structure.
/// \param ptUserData The user-set structure containing all the hardware parameters.
bool GetMACIEClockRate(MACIE_Settings *ptUserData)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    unsigned int val = 0;

    // Get MACIE Clock Speed
    // verbose_printf(LOG_INFO, ptUserData, "Get MACIE clock rate....\n");
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, 0x0010, &val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_ReadMACIEReg failed: %s\n", MACIE_Error());
            return false;
        }
        // Below 0x6f (DEC 111), 1 MHZ is a change of 4 values
        // Above 0x6f (DEC 111), 1 MHZ is a change of 2 values
        ptUserData->clkRateM = (val < 111) ? (val + 1) / 4 : (val - 55) / 2;
    }

    // Update pixel rate information
    if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
    {
        // clkRateM in MHz to kHz pixel rate
        // For instance, 10MHz master clock corresponds to 100 khz pixel rate
        ptUserData->pixelRate = ptUserData->clkRateM * 10;
    }
    else
    {
        // For Fast Mode
        //   80 Mhz -> 10000 kHz pixel rate (H1RG)
        //   80 Mhz ->  5000 kHz pixel rate (H2RG, H4RG)
        ptUserData->pixelRate = (1000 * ptUserData->clkRateM) / 8;
        if (ptUserData->DetectorType != CAMERA_TYPE_H1RG)
            ptUserData->pixelRate /= 2;
    }

    // verbose_printf(LOG_INFO,  ptUserData, "  Succeeded.\n");
    verbose_printf(LOG_INFO, ptUserData, "  MACIE Clock Rate = %i MHz\n", ptUserData->clkRateM);
    verbose_printf(LOG_INFO, ptUserData, "  Detector Pixel Rate = %i kHz\n", ptUserData->pixelRate);

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief GetVoltages Print voltages or current for each MACIE Power DAC.
/// \param ptUserData The user-set structure containing all the hardware parameters
/// \param vArr[] Output pointer array holding voltages/currents
bool GetVoltages(MACIE_Settings *ptUserData, float vArr[])
{

    string names[MACIE_PWR_DAC_SIZE] = {"VREF1",
                                        "VDDAHIGH1", "VDDAHIGH1_VL", "VDDAHIGH1_CL",
                                        "VDDALOW1", "VDDALOW1_VL", "VDDALOW1_CL",
                                        "VDDHIGH1", "VDDHIGH1_VL", "VDDHIGH1_CL",
                                        "VDDLOW1", "VDDLOW1_VL", "VDDLOW1_CL",
                                        "VDDIO1", "VDDIO1_VL", "VDDIO1_CL",
                                        "VSSIO1", "VSSIO1_VL",
                                        "VDDAUX1",
                                        "VREF2",
                                        "VDDAHIGH2", "VDDAHIGH2_VL", "VDDAHIGH2_CL",
                                        "VDDALOW2", "VDDALOW2_VL", "VDDALOW2_CL",
                                        "VDDHIGH2", "VDDHIGH2_VL", "VDDHIGH2_CL",
                                        "VDDLOW2", "VDDLOW2_VL", "VDDLOW2_CL",
                                        "VDDIO2", "VDDIO2_VL", "VDDIO2_CL",
                                        "VSSIO2", "VSSIO2_VL",
                                        "VDDAUX2"};

    float fval = 0.0;
    verbose_printf(LOG_NONE, ptUserData, "MACIE Power DAC Values:\n");
    for (int i = 0; i < MACIE_PWR_DAC_SIZE; i++)
    {
        if (ptUserData->offline_develop == false)
        {
            if (MACIE_GetVoltage(ptUserData->handle, ptUserData->slctMACIEs, MACIE_PWR_DAC(i), &fval) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData, "MACIE_GetVoltage failed in %s\n", __func__);
                return false;
            }
        }

        vArr[i] = fval;
        verbose_printf(LOG_NONE, ptUserData, "%15s = %.2f %s\n", names[i].c_str(), vArr[i],
                       (names[i].substr(names[i].length() - 2) == "CL") ? "mA" : "V");
    }
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief GetPower Print on/off status for each MACIE Power Control item.
/// \param ptUserData The user-set structure containing all the hardware parameters
/// \param pArr[] Output pointer array indicating which elements are on/off
bool GetPower(MACIE_Settings *ptUserData, bool pArr[])
{

    string names[MACIE_PWR_CTRL_SIZE] = {"5V_ASIC",
                                         "GIGE", "GIGE_OVERRIDE",
                                         "DGND_FILTER_BYPASS",
                                         "USB_FILTER_BYPASS",
                                         "AGND_CLEAN_FILTER_BYPASS",
                                         "AGND_DIRTY_FILTER_BYPASS",
                                         "VDDAUX1", "VDDAUX2",
                                         "VDDAHIGH1", "VDDALOW1", "VREF1",
                                         "SENSE_VREF1_GNDA",
                                         "SENSE_VDDAHIGH1_GNDA", "SENSE_VDDAHIGH1",
                                         "SENSE_VDDALOW1_GNDA", "SENSE_VDDALOW1",
                                         "VDDHIGH1", "VDDLOW1",
                                         "VDDIO1", "VSSIO1",
                                         "SENSE_VDDHIGH1_GND", "SENSE_VDDHIGH1",
                                         "SENSE_VDDLOW1_GND", "SENSE_VDDLOW1",
                                         "VDDAHIGH2", "VDDALOW2", "VREF2",
                                         "SENSE_VREF2_GNDA",
                                         "SENSE_VDDAHIGH2_GNDA", "SENSE_VDDAHIGH2",
                                         "SENSE_VDDALOW2_GNDA", "SENSE_VDDALOW2",
                                         "VDDHIGH2", "VDDLOW2",
                                         "VDDIO2", "VSSIO2",
                                         "SENSE_VDDHIGH2_GND", "SENSE_VDDHIGH2",
                                         "SENSE_VDDLOW2_GND", "SENSE_VDDLOW2"};

    bool bEn = true;
    verbose_printf(LOG_NONE, ptUserData, "MACIE Power Control Settings:\n");
    for (int i = 0; i < MACIE_PWR_CTRL_SIZE; i++)
    {
        if (ptUserData->offline_develop == false)
        {
            if (MACIE_GetPower(ptUserData->handle, ptUserData->slctMACIEs, MACIE_PWR_CTRL(i), &bEn) != MACIE_OK)
            {
                verbose_printf(LOG_ERROR, ptUserData, "MACIE_GetPower failed in %s\n", __func__);
                return false;
            }
        }

        pArr[i] = bEn;
        verbose_printf(LOG_NONE, ptUserData, "%25s = %s\n", names[i].c_str(),
                       (pArr[i] == true) ? "ON" : "OFF");
    }

    return true;
}

bool GetPowerASIC(MACIE_Settings *ptUserData, bool *bEn)
{
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_GetPower(ptUserData->handle, ptUserData->slctMACIEs, MACIE_CTRL_5V_ASIC, bEn) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_GetPower failed in %s\n", __func__);
            return false;
        }
    }
    else
    {
        *bEn = true;
    }
    verbose_printf(LOG_INFO, ptUserData, "ASIC is powered %s.\n", *bEn ? "ON" : "OFF");

    return true;
}

bool SetPowerASIC(MACIE_Settings *ptUserData, bool bEn)
{
    unsigned int reg = 0x0300;
    unsigned int val = 0;
    unsigned int bitmask = 1;

    if (ptUserData->offline_develop == false)
    {

        // Read MACIE 0x0300 and store in val
        if (MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, reg, &val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "Initial MACIE_ReadMACIEReg (h%04x) failed in %s\n",
                           reg, __func__);
            return false;
        }
    }
    else
    {
        val = 0x3;
    }

    if (bEn == true)
        val |= bitmask; // Enable bit0
    else
        val &= ~bitmask; // Clear bit0
    verbose_printf(LOG_DEBUG, ptUserData, "Writing to MACIE: h%04x = 0x%04x\n", reg, val);

    if (ptUserData->offline_develop == false)
    {
        // Write new value with bit0 cleared
        if (MACIE_WriteMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, reg, val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_WriteMACIEReg (h%04x) failed in %s\n", reg, __func__);
            return false;
        }

        // Confirm bit0 has been written correctly
        if (MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, reg, &val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_ReadMACIEReg (h%04x) failed in %s\n", reg, __func__);
            return false;
        }

        val &= bitmask; // AND mask of bit0
        if ((bEn == false && val == 1) || (bEn == true && val == 0))
        {
            verbose_printf(LOG_ERROR, ptUserData, "ASIC failed to power %s.\n", bEn ? "on" : "off");
            return false;
        }
    }

    // Print out MACIE power settings
    if (GetPowerASIC(ptUserData, &bEn) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "GetPowerASIC failed in %s\n", __func__);
        return false;
    }

    // verbose_printf(LOG_INFO, ptUserData, "ASIC succesfully powered %s.\n", bEn ? "on" : "off");
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief SetLED Set brightness of MACIE's status LEDs. This writes to MACIE
///  register 0x000a on bits 0, 1, and 2. Setting bit2=1 turns off LEDS.
///  Setting bits 0 and 1 to values 0,1,2, or 3 changes the LED brightness.
/// \param ptUserData The user-set structure containing all the hardware parameters
/// \param set_val A alue 0-4, where 0 is off and 1-4 is faintest to brightest
bool SetLED(MACIE_Settings *ptUserData, unsigned int set_val)
{

    unsigned int reg = 0x000a;
    unsigned int reg_val = 0;
    unsigned int bitmask = 0;

    if (ptUserData->offline_develop == false)
    {

        // Read MACIE 0x000a and store in reg_val
        if (MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, reg, &reg_val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "Initial MACIE_ReadMACIEReg (h%04x) failed in %s\n", reg, __func__);
            return false;
        }
    }
    else
    {
        reg_val = 0x3;
    }

    // Clear first three bits
    // bit2 controls
    bitmask = 0x7;
    reg_val &= ~bitmask;

    // Determine val to write to MACIE
    if (set_val == 0)
    { // Power off
        bitmask = 0x4;
    }
    else if (set_val <= 4)
    { // Power on (bit2=0) with bits 0 and 1 values being 0-3
        bitmask = set_val - 1;
    }
    else
    { // Any other setting, max brightness
        bitmask = 0x3;
    }

    // Enable bits set in bitmask
    reg_val |= bitmask;
    verbose_printf(LOG_DEBUG, ptUserData, "Writing to MACIE: h%04x = 0x%04x\n", reg, reg_val);

    if (ptUserData->offline_develop == false)
    {
        // Write new value
        if (MACIE_WriteMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, reg, reg_val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_WriteMACIEReg (h%04x) failed in %s\n", reg, __func__);
            return false;
        }

        // Confirm bit0 has been written correctly
        if (MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, reg, &reg_val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_ReadMACIEReg (h%04x) failed in %s\n", reg, __func__);
            return false;
        }
        // Clear all but first three bits and check if equal to bitmask
        reg_val &= 0x7;
        if (reg_val != bitmask)
        {
            verbose_printf(LOG_ERROR, ptUserData, "reg_val (%i) != bitmask (%i) \n", reg_val, bitmask);
            return false;
        }
    }

    verbose_printf(LOG_INFO, ptUserData, "ASIC LED power set succesfully to %i.\n", set_val);
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief SetMACIEClockRate Set the MACIE master clock rate.
/// \param ptUserData The user-set structure containing all hardware parameters.
/// \param clkRateM Value to set clock rate in MHz.
bool SetMACIEClockRate(MACIE_Settings *ptUserData, unsigned int clkRateM)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Check that clkRateM is valid
    // Slow: [5-50] (5-500 kHz pixel rate)
    // Fast: [8-80] (0.5-5 MHz pixel rate)
    if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
    {
        if ((clkRateM < 5) || (clkRateM > 50))
        {
            verbose_printf(LOG_ERROR, ptUserData,
                           "SetMACIEClockRate value (%i MHz) out of range (5-50)\n", clkRateM);
            return false;
        }
    }
    else
    {
        if ((clkRateM < 8) || (clkRateM > 80))
        {
            verbose_printf(LOG_ERROR, ptUserData,
                           "SetMACIEClockRate value (%i MHz) out of range (8-80)\n", clkRateM);
            return false;
        }
    }

    // Set MACIE Clock Speed
    unsigned int val = 0;
    verbose_printf(LOG_INFO, ptUserData, "Set MACIE clock rate to %i MHz\n", clkRateM);

    // Convert clock rate in MHz to register value
    val = (clkRateM < 28) ? (4 * clkRateM) - 1 : (2 * clkRateM) + 55;
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_WriteMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, 0x0010, val) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_WriteMACIEReg failed: %s\n", MACIE_Error());
            return false;
        }
    }

    // If we've succeeded, then save value to ptUserData
    ptUserData->clkRateM = clkRateM;
    GetMACIEClockRate(ptUserData);

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief GetMACIEPhaseShift Get the current ASIC clock phase shift setting
/// from the MACIE card.
/// \param ptUserData The user-set structure containing all hardware parameters.
bool GetMACIEPhaseShift(MACIE_Settings *ptUserData)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Get MACIE Clock Phase Shift
    verbose_printf(LOG_INFO, ptUserData, "Get MACIE clock phase parameters....\n");
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_GetMACIEPhaseShift(ptUserData->handle, ptUserData->slctMACIEs, &ptUserData->clkPhase) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_GetMACIEPhaseShift failed: %s\n", MACIE_Error());
            return false;
        }
    }
    verbose_printf(LOG_INFO, ptUserData, "  clkPhase = 0x%04x\n", ptUserData->clkPhase);

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief SetMACIEPhaseShift Optimize the ASIC clock phase for science data
/// transmission from ASIC to MACIE. Normally is function is only used for ASIC
/// fast mode application.
/// \param ptUserData The user-set structure containing all the parameters
/// for the hardware.
/// \param clkPhase ASIC clock phase setting register value.
bool SetMACIEPhaseShift(MACIE_Settings *ptUserData, unsigned short clkPhase)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Set MACIE Clock Phase Shift
    verbose_printf(LOG_INFO, ptUserData, "Set MACIE clkPhase = 0x%04x\n", clkPhase);
    if (ptUserData->offline_develop == false)
    {
        if (MACIE_SetMACIEPhaseShift(ptUserData->handle, ptUserData->slctMACIEs, clkPhase) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_SetMACIEPhaseShift failed: %s\n", MACIE_Error());
            return false;
        }
    }

    // If we've succeeded, then save value to ptUserData
    ptUserData->clkPhase = clkPhase;
    // verbose_printf(LOG_INFO, ptUserData, "  Succeeded.\n");
    verbose_printf(LOG_DEBUG, ptUserData, "  clkPhase = 0x%04x\n", ptUserData->clkPhase);

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief ToggleMACIEPhaseShift Toggle clock phase shifting on or off.
/// \param ptUserData The user-set structure containing all the parameters
/// for the hardware.
/// \param enable Enable clock phase shifting; true or false.
bool ToggleMACIEPhaseShift(MACIE_Settings *ptUserData, bool enable)
{
    unsigned short pos = 8; // Bit 8 controls whether or not Phase Shift is enabled
    unsigned short newPhase = 0;
    bool bit; // Used to check if already enabled

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Assume ptUserData->clkPhase accurately represents hardware state
    bit = (ptUserData->clkPhase >> pos) & 1U;
    if (bit == enable)
    {
        verbose_printf(LOG_WARNING, ptUserData, "Phase Shift already %s. Returning.\n",
                       (enable == true) ? "enabled" : "disabled");
        return true;
    }

    // Update clkPhase parameter
    newPhase = (enable == true) ? ptUserData->clkPhase | (1UL << pos) : // Toggle bit 8 to on
                   ptUserData->clkPhase & ~(1UL << pos);                // Toggle bit 8 to off

    verbose_printf(LOG_INFO, ptUserData, "%s Clock Phase Shift\n",
                   (enable == true) ? "Enabling" : "Disabling");
    // clkPhase is updated inside SetMACIEPhaseShift
    return SetMACIEPhaseShift(ptUserData, newPhase);
}

bool FindOptimalPhaseShift(MACIE_Settings *ptUserData, ushort val_start, ushort val_end)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Make sure Clock Phase Shift bit is enabled (bit 8)
    val_start |= (1UL << 8);
    val_end |= (1UL << 8);
    if (val_start > val_end)
    {
        verbose_printf(LOG_ERROR, ptUserData, "val_start must be less than val_end\n");
        return false;
    }

    // Current values to revert to at the end
    bool bSaveTemp = ptUserData->bSaveData;
    ushort usCPTemp = ptUserData->clkPhase;
    LOG_LEVEL llTemp = get_verbose(ptUserData);

    // Don't saving and only print error messages
    ptUserData->bSaveData = false;
    set_verbose(ptUserData, LOG_ERROR);

    // Variable to hold error counts
    uint errCnts = 0;

    // First and last values where err counts = 0
    ushort val0_1 = 0;
    ushort val0_2 = 0;

    // Increment through each value
    for (ushort i = val_start; i < val_end + 1; i++)
    {
        // Reset Error Counters
        if (ResetErrorCounters(ptUserData) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "ResetErrorCounters failed at %s\n", __func__);
            ptUserData->bSaveData = bSaveTemp;
            set_verbose(ptUserData, llTemp);
            return false;
        }
        // Set the Phase Shift value
        if (SetMACIEPhaseShift(ptUserData, i) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData,
                           "SetMACIEPhaseShift failed at %s with clkPhase = 0x%04x\n", __func__, i);
            ptUserData->bSaveData = bSaveTemp;
            set_verbose(ptUserData, llTemp);
            GetErrorCounters(ptUserData, true);
            return false;
        }

        // Acquire exposures
        if (AcquireDataUSB(ptUserData, false) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "AcquireDataUSB failed at %s()\n", __func__);
            ptUserData->bSaveData = bSaveTemp;
            set_verbose(ptUserData, llTemp);
            GetErrorCounters(ptUserData, true);
            return false;
        }
        // Download data (will not be saved)
        if (DownloadAndSaveAllUSB(ptUserData) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "DownloadAndSaveAllUSB failed at %s()\n", __func__);
            ptUserData->bSaveData = bSaveTemp;
            set_verbose(ptUserData, llTemp);
            GetErrorCounters(ptUserData, true);
            return false;
        }

        // Download Error Counters and check ASIC errors
        if (GetErrorCounters(ptUserData, false) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "GetErrorCounters failed at %s()\n", __func__);
            ptUserData->bSaveData = bSaveTemp;
            set_verbose(ptUserData, llTemp);
            return false;
        }
        // Sum all error counts for ASIC Science
        errCnts = TotalErrorCounts(ptUserData);
        fprintf(stderr, "  0x%04x  %i\n", i, errCnts);

        if (errCnts == 0)
        {
            if (val0_1 == 0)
                val0_1 = i;

            val0_2 = i;
        }
    }

    ResetErrorCounters(ptUserData);

    // Recommended value
    fprintf(stderr, "Recommended Value: 0x%04x\n", val0_1 + (val0_2 - val0_1 + 1) / 2);

    // Revert back to original value
    ptUserData->bSaveData = bSaveTemp;
    SetMACIEPhaseShift(ptUserData, usCPTemp);
    set_verbose(ptUserData, llTemp);
    return true;
}

// Return total number of errors in errArr
unsigned int TotalErrorCounts(MACIE_Settings *ptUserData)
{
    uint errCnts = 0;
    for (int j = 0; j < MACIE_ERROR_COUNTERS; j++)
        errCnts += (uint)ptUserData->errArr[j];
    return errCnts;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief GetErrorCounters Read MACIE error counter registers.
/// \param ptUserData The user-set structure containing the hardware parameters.
/// \param bVerb A more verbose output describing error counter sections.
bool GetErrorCounters(MACIE_Settings *ptUserData, bool bVerb)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (ptUserData->offline_develop == false)
    {
        if (MACIE_GetErrorCounters(ptUserData->handle, ptUserData->slctMACIEs, ptUserData->errArr) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_GetErrorCounters failed: %s\n", MACIE_Error());
            return false;
        }
    }

    // 1. UART Parity Errors
    // 2. UART Stopbit Errors
    // 3. UART Timeout Errors
    // 4. USB Timeout Errors
    // 5. GigE Timeout Errors
    // 6-13 ASIC 1 configuration interface errors
    // 14-21 ASIC 2 configuration interface errors
    // 22-25 FIFO errors (e.g. overflow of main FIFO at 22)
    // 26-29 ASIC 1 science interface errors
    // 30-33 ASIC 2 science interface errors

    if (bVerb)
    {
        fprintf(stderr, "  UART (Parity, Stopbit, Timout) = (");
        for (int i = 0; i < 3; i++)
            fprintf(stderr, " %04x", ptUserData->errArr[i]);
        fprintf(stderr, " )\n");

        fprintf(stderr, "  (USB, GigE) Timout = (");
        for (int i = 3; i < 5; i++)
            fprintf(stderr, " %04x", ptUserData->errArr[i]);
        fprintf(stderr, " )\n");

        fprintf(stderr, "  ASIC1 Config  = (");
        for (int i = 5; i < 13; i++)
            fprintf(stderr, " %04x", ptUserData->errArr[i]);
        fprintf(stderr, " )\n");

        fprintf(stderr, "  ASIC2 Config  = (");
        for (int i = 13; i < 21; i++)
            fprintf(stderr, " %04x", ptUserData->errArr[i]);
        fprintf(stderr, " )\n");

        fprintf(stderr, "  FIFO errors   = (");
        for (int i = 21; i < 25; i++)
            fprintf(stderr, " %04x", ptUserData->errArr[i]);
        fprintf(stderr, " )\n");

        fprintf(stderr, "  ASIC1 Science = (");
        for (int i = 25; i < 29; i++)
            fprintf(stderr, " %04x", ptUserData->errArr[i]);
        fprintf(stderr, " )\n");

        fprintf(stderr, "  ASIC2 Science = (");
        for (int i = 29; i < 33; i++)
            fprintf(stderr, " %04x", ptUserData->errArr[i]);
        fprintf(stderr, " )\n");
    }

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief ResetErrorCounters Reset MACIE error counter registers.
/// \param ptUserData The user-set structure containing the hardware parameters.
bool ResetErrorCounters(MACIE_Settings *ptUserData)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (ptUserData->offline_develop == false)
    {
        if (MACIE_ResetErrorCounters(ptUserData->handle, ptUserData->slctMACIEs) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_ResetErrorCounters failed: %s\n", MACIE_Error());
            return false;
        }
    }
    // Set all error counters to 0 if success
    std::fill_n(ptUserData->errArr, MACIE_ERROR_COUNTERS, 0);

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief ReadASICReg Read ASIC register.
/// \param ptUserData The user-set structure containing the hardware parameters.
/// \param addr Register address
/// \param val Pointer or value read from the address (output).
bool ReadASICReg(MACIE_Settings *ptUserData, unsigned short addr, unsigned int *val)
{
    unsigned short ntry = 3;

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Try a few times and return if successful
    if (ptUserData->offline_develop == false)
    {
        for (int i = 0; i < ntry; i++)
        {
            // TODO: Maybe put in a slight delay between reads?
            // If read is succesful, then return true
            delay(10);
            if (MACIE_ReadASICReg(ptUserData->handle, ptUserData->slctASICs, addr, val, false, true) == MACIE_OK)
            {
                verbose_printf(LOG_DEBUG, ptUserData, " ReadASICReg h%04x = 0x%04x\n", addr, *val);
                return true;
            }
            // if not successful and we haven't hit the last iteration,
            // then ResetErrorCounters (which could also fail)
            else if (i < ntry - 1)
            {
                if (ResetErrorCounters(ptUserData) == false)
                    break;
            }
        }
    }
    else
    {
        string addr_name = addr_name_hex(addr);
        *val = ptUserData->RegAllASIC[addr_name].value;
        verbose_printf(LOG_DEBUG, ptUserData, "  %s: h%04x = 0x%04x\n", __func__, addr, *val);

        return true;
    }

    // If we've gotten here, then we were not successful
    verbose_printf(LOG_ERROR, ptUserData, "MACIE_ReadASICReg failed: %s\n", MACIE_Error());
    return false;
}

bool ReadASICBits(MACIE_Settings *ptUserData, regInfo *reg, unsigned int *val)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Read the ASIC registers
    if (ReadASICReg(ptUserData, reg->addr, val) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "ReadASICReg failed in %s\n", __func__);
        return false;
    }

    // Number of bits
    unsigned int nbits = reg->bit1 - reg->bit0 + 1;
    *val >>= reg->bit0;       // Shift val bits to the right
    *val &= (1 << nbits) - 1; // Bitwise AND with a bitmask

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief ReadASICBlock Read a number of contiguous registers starting at the
/// specified register address.
/// \param ptUserData The user-set structure containing the hardware parameters.
/// \param addr ASIC register address to start reading (ie., 0x6000)
/// \param nreg Number of ASIC registers to read
/// \param val Pointer or address of array storing the readback register values.
bool ReadASICBlock(MACIE_Settings *ptUserData, unsigned short addr, int nreg,
                   unsigned int *val_arr)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (ptUserData->offline_develop == false)
    {
        if (MACIE_ReadASICBlock(ptUserData->handle, ptUserData->slctASICs, addr, val_arr, nreg, false, true) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_ReadASICBlock failed: %s\n", MACIE_Error());
            return false;
        }
    }
    else
    {
        string addr_name;
        // unsigned int val_arr[nreg];
        for (int i = 0; i < nreg; i++)
        {
            // Convert decimal addr to hex string
            addr_name = addr_name_hex(addr + i);
            val_arr[i] = ptUserData->RegAllASIC[addr_name].value;
        }
    }

    for (int i = 0; i < nreg; i++)
        verbose_printf(LOG_DEBUG, ptUserData, "  %s: h%04x = 0x%04x\n", __func__, addr + i, val_arr[i]);

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief WriteASICReg Write value to ASIC register.
/// \param addr Register address
/// \param val Value to write to the register address.
bool WriteASICReg(MACIE_Settings *ptUserData, unsigned short addr, unsigned int val)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (ptUserData->offline_develop == false)
    {
        if (MACIE_WriteASICReg(ptUserData->handle, ptUserData->slctASICs, addr, val, true) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_WriteASICReg failed: %s\n", MACIE_Error());
            return false;
        }
        // verbose_printf(LOG_DEBUG, ptUserData, "WriteASICReg: h%04x, 0x%04x\n", addr, val);
        verbose_printf(LOG_DEBUG, ptUserData, "  %s: h%04x = 0x%04x\n", __func__, addr, val);
    }
    else
    {
        // Convert decimal addr to hex string
        string addr_name = addr_name_hex(addr);
        ptUserData->RegAllASIC[addr_name] = gen_regInfo(addr, 0, 15, val);
        verbose_printf(LOG_DEBUG, ptUserData, "  %s: h%04x = 0x%04x\n", __func__, addr, val);
    }

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief WriteASICBits Write only specified bits of a register
/// \param ptUserData The user-set structure containing all the parameters
/// for the hardware.
/// \param reg Register info structure {address, bit0, bit1, value}
bool WriteASICBits(MACIE_Settings *ptUserData, regInfo *reg)
{
    unsigned int regval = 0;
    unsigned int bitmask = 0;
    unsigned int nbits = 0;

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Read the ASIC registers
    if (ReadASICReg(ptUserData, reg->addr, &regval) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "ReadASICReg failed in %s\n", __func__);
        return false;
    }

    // Create bitmask
    nbits = reg->bit1 - reg->bit0 + 1;
    bitmask = (1 << nbits) - 1;
    // Ensure input reg.value indeed only covers that many bits
    reg->value &= bitmask;

    // Shift bitmask and clear bits
    regval &= ~(bitmask << reg->bit0);

    // Replace cleared bits with reg.value
    regval |= reg->value << reg->bit0;

    // Write final ASIC registers
    if (WriteASICReg(ptUserData, reg->addr, regval) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "WriteASICReg failed in %s\n", __func__);
        return false;
    }

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief WriteASICBlock Write a number of contiguous registers starting at the
/// specified register address.
/// \param addr ASIC register address to start writing (ie., 0x6000)
/// \param nreg Number of ASIC registers to write to
/// \param val Pointer or address of array storing the register write values.
bool WriteASICBlock(MACIE_Settings *ptUserData, unsigned short addr, int nreg,
                    unsigned int *val)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (ptUserData->offline_develop == false)
    {
        if (MACIE_WriteASICBlock(ptUserData->handle, ptUserData->slctASICs, addr, val, nreg, true) != MACIE_OK)
        {
            verbose_printf(LOG_ERROR, ptUserData, "MACIE_WRiteASICBlock failed: %s\n", MACIE_Error());
            return false;
        }
    }
    else
    {
        // Update stored registers
        string addr_name;
        for (int i = 0; i < nreg; i++)
        {
            addr_name = addr_name_hex(addr + i);
            ptUserData->RegAllASIC[addr_name] = gen_regInfo(addr, 0, 15, val[i]);
        }
    }

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief GetASICSettings Grab all ASIC register settings defined in RegMap
/// mapped dictionary, which exists inside UserData settings.
/// \param ptUserData The user-set structure containing all the parameters
/// for the hardware.
bool GetASICSettings(MACIE_Settings *ptUserData)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    map<string, regInfo>::iterator it;
    unsigned int val = 0;
    regInfo *reg;

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // verbose_printf(LOG_INFO, ptUserData, "Reading ASIC registers...\n");
    for (it = RegMap.begin(); it != RegMap.end(); it++)
    {
        reg = &it->second;

        // Read the ASIC registers
        // TODO: Maybe put in a slight delay between reads?
        if (ReadASICBits(ptUserData, reg, &val) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "ReadASICBits failed in %s\n", __func__);
            return false;
        }
        reg->value = val;

        verbose_printf(LOG_DEBUG, ptUserData, "%s : h%04x <%i:%i> = %i\n",
                       it->first.c_str(), reg->addr, reg->bit1, reg->bit0, reg->value);
    }

    verbose_printf(LOG_INFO, ptUserData, "Succeeded reading ASIC registers.\n");
    return true;
}

// NumResets       0x4000  0  15   # NReset
// NumReads        0x4001  0  15   # NRead in each Group
// NumDrops        0x4005  0  15   # NDrop between consecutive Groups
// NumGroups       0x4004  0  15   # NGroups
// NumRamps        0x4003  0  15   # NRamps
// ExtraPixels     0x4006  0  15   # Number of extra pixel times added per row
// ExtraLines      0x4007  0  15   # Number of extra rows added per frame

////////////////////////////////////////////////////////////////////////////////
/// \brief SetASICParameter Modify ASIC parameters as defined in .cfg files.
///  This function only modifies those relevant bits (bits0 to bit1)
/// \param ptUserData The user-set structure containing the hardware parameters.
/// \param addr_name Name of parameter to modify, such as NumReads or VReset1
/// \param val Value to set parameter
bool SetASICParameter(MACIE_Settings *ptUserData, string addr_name, unsigned int val)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    map<string, regInfo> &RegMap = ptUserData->RegMap;

    // Check if addr_name key exists
    // If it's not valid, throw warning, but return true.
    if (RegMap.count(addr_name) == 0)
    {
        verbose_printf(LOG_WARNING, ptUserData,
                       "Parameter name %s does not exist in Register Map.\n", addr_name.c_str());
        return false;
    }

    regInfo *reg = &RegMap[addr_name];
    regInfo regNew = gen_regInfo(reg->addr, reg->bit0, reg->bit1, val);
    unsigned int valOut;

    // Check if desired value is different than current value
    // If so, then just return
    if (ReadASICBits(ptUserData, reg, &valOut) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "ReadASICBits failed in %s\n", __func__);
        return false;
    }
    if (val == valOut)
    {
        reg->value = valOut;
        return true;
    }

    // Write ASIC register
    if (WriteASICBits(ptUserData, &regNew) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData,
                       "WriteASICBits failed to write %s in %s\n", addr_name.c_str(), __func__);
        return false;
    }

    // Read the updated ASIC register value
    if (ReadASICBits(ptUserData, reg, &valOut) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "ReadASICBits failed in %s\n", __func__);
        return false;
    }

    // Verify ASIC reg value matches input
    if (val != valOut)
    {
        verbose_printf(LOG_ERROR, ptUserData,
                       "Write value of %i (0x%04x) does not match ASIC read value of %i (0x%04x) for %s in %s.\n",
                       val, val, valOut, valOut, addr_name.c_str(), __func__);
        return false;
    }

    verbose_printf(LOG_INFO, ptUserData, "Updated %s from %i (0x%04x) to %i (0x%04x).\n",
                   addr_name.c_str(), reg->value, reg->value, valOut, valOut);

    reg->value = valOut;
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief GetASICParameter Obtain ASIC parameters as defined in .cfg files.
///  This function only reads current ASIC setting stored in RegMap.
/// \param ptUserData The user-set structure containing the hardware parameters.
/// \param addr_name Name of parameter to read, such as NumReads or VReset1.
/// \param val Value output.
bool GetASICParameter(MACIE_Settings *ptUserData, string addr_name, unsigned int *val)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    map<string, regInfo> &RegMap = ptUserData->RegMap;

    // Check if addr_name key exists
    if (RegMap.count(addr_name) == 0)
    {
        verbose_printf(LOG_ERROR, ptUserData,
                       "Parameter name %s does not exist in Register Map.\n", addr_name.c_str());
        return false;
    }

    // Assume RegMap accurately reflects current state of ASIC registries
    // Allows us to grab measurements if USB pipe is being used by data download.
    regInfo *reg = &RegMap[addr_name];
    *val = reg->value;
    // unsigned int valOut;

    // // Read the ASIC register value
    // if (ReadASICBits(ptUserData, reg, &valOut)==false)
    // {
    //   verbose_printf(LOG_ERROR, ptUserData, "ReadASICBits failed in %s\n", __func__);
    //   return false;
    // }

    // // Store in ptUserData->RegMap
    // reg->value = valOut;
    // *val = reg->value;

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// ASIC convenience functions
////////////////////////////////////////////////////////////////////////////////
unsigned int ASIC_Generic(MACIE_Settings *ptUserData, string addr_name, bool bSet, unsigned int val)
{
    if (bSet == true)
    {
        if (SetASICParameter(ptUserData, addr_name, val) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "SetASICParameter (addr_name=%s) failed at %s()\n",
                           addr_name.c_str(), __func__);
            val = 0;
        }
    }
    else
    {
        if (GetASICParameter(ptUserData, addr_name, &val) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "GetASICParameter (addr_name=%s) failed at %s()\n",
                           addr_name.c_str(), __func__);
            val = 0;
        }
    }
    verbose_printf(LOG_DEBUG, ptUserData, "  %s(): %s returns %i\n", __func__, addr_name.c_str(), val);
    return val;
}
unsigned int ASIC_NResets(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if ((bSet == true) && (val < 1))
    {
        verbose_printf(LOG_ERROR, ptUserData, "NumResets should be >0. Setting to 1.\n");
        val = 1;
    }
    return ASIC_Generic(ptUserData, "NumResets", bSet, val);
}
unsigned int ASIC_NReads(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if ((bSet == true) && (val < 1))
    {
        verbose_printf(LOG_ERROR, ptUserData, "NumReads should be >0. Setting to 1.\n");
        val = 1;
    }
    return ASIC_Generic(ptUserData, "NumReads", bSet, val);
}
unsigned int ASIC_NDrops(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    return ASIC_Generic(ptUserData, "NumDrops", bSet, val);
}
unsigned int ASIC_NGroups(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if ((bSet == true) && (val < 1))
    {
        verbose_printf(LOG_ERROR, ptUserData, "NumGroups should be >0. Setting to 1.\n");
        val = 1;
    }
    return ASIC_Generic(ptUserData, "NumGroups", bSet, val);
}
unsigned int ASIC_NRamps(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if ((bSet == true) && (val < 1))
    {
        verbose_printf(LOG_ERROR, ptUserData, "NumRamps should be >0. Setting to 1.\n");
        val = 1;
    }
    return ASIC_Generic(ptUserData, "NumRamps", bSet, val);
}
unsigned int ASIC_NCoadds(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if ((bSet == true) && (val < 1))
    {
        verbose_printf(LOG_ERROR, ptUserData, "NumCoadds should be >0. Setting to 1.\n");
        val = 1;
    }

    if (bSet == true)
    {
        ptUserData->uiNumCoadds = val;
    }
    else
    {
        val = ptUserData->uiNumCoadds;
    }
    return val;
}
unsigned int ASIC_NSaves(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if ((bSet == true) && (val < 1))
    {
        verbose_printf(LOG_ERROR, ptUserData, "uiNumSaves should be >0. Setting to 1.\n");
        val = 1;
    }

    if (bSet == true)
    {
        ptUserData->uiNumSaves = val;
    }
    else
    {
        val = ptUserData->uiNumSaves;
    }
    return val;
}

// Return the number of frames in exposure (either just frames for d/l or all w/ resets+drops)
// If include_all=false, then only include number of saved frames (reads + maybe resets)
unsigned int exposure_nframes(MACIE_Settings *ptUserData, bool include_all)
{
    unsigned int nramps = ASIC_NRamps(ptUserData, false, 0);
    unsigned int ngroups = ASIC_NGroups(ptUserData, false, 0);
    unsigned int nreads = ASIC_NReads(ptUserData, false, 0);
    unsigned int ndrops = 0;
    unsigned int nresets = 0;

    // Saving reset frames?
    unsigned int val = 0;
    if (GetASICParameter(ptUserData, "SaveRstFrames", &val) == true)
        if (val == 1)
            nresets = ASIC_NResets(ptUserData, false, 0);

    if (include_all)
    {
        ndrops = ASIC_NDrops(ptUserData, false, 0);
        nresets = ASIC_NResets(ptUserData, false, 0);
    }

    return nramps * (ngroups * nreads + (ngroups - 1) * ndrops + nresets);
}

// Input desired ramp integration time in millisec (tint_ms) and maximum number of groups.
// Returns the total number of groups and drops to obtain tint_ms.
// NReads is always assumed to be 1. Ramp time increased by adding drop frames.
bool calc_ramp_settings(MACIE_Settings *ptUserData, double tint_ms, int ngmax,
                        uint *ngroups, uint *ndrops, uint *nreads)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (ngmax <= 0)
        ngmax = ptUserData->uiNumGroups_max;

    // Special case, single frame
    double ftime_ms = ptUserData->frametime_ms;
    if (tint_ms < ftime_ms)
    {
        *ngroups = 1;
        *nreads = 1;
        *ndrops = 0;
        return true;
    }

    // Total number of requested frames based on ramp integration time
    int nftot = (int)ceil(tint_ms / ftime_ms);
    int nr = 1;
    int nd = 0;
    int ng = 2;

    // Special case, 2 groups
    if ((ngmax == 2) || (ngmax == 1))
    {
        if (ngmax == 1)
            verbose_printf(LOG_WARNING, ptUserData,
                           "Maximum number of groups must be greater than or equal to 2\n");
        ng = 2;
        nd = nftot - (ng * nr);
        *ngroups = ng;
        *nreads = nr;
        *ndrops = nd;
        return true;
    }

    // More requested frames that groups
    // Need to insert drop frames into each group
    // Optimize ndrops and ngroups to obtain request int time
    if (nftot > ngmax)
    {
        int nftot_res = 0, ngmin = 0;
        double frac = 1.0, nf_diff = 0.0;
        ngmin = (ngmax <= 3) ? ngmax - 1 : 2;

        int ng_best = 0, nd_best = 0;
        double nf_diff_prev = 10.0;
        double frac_prev = 1.0;

        for (int i = ngmax; i > ngmin; --i)
        {
            ng = i;
            nd = ceil((tint_ms / ftime_ms - (ng * nr)) / (ng - 1));
            nftot_res = ng * nr + (ng - 1) * nd;

            // Break conditions
            nf_diff = (double)nftot_res - (tint_ms / ftime_ms);
            frac = nf_diff * ftime_ms / tint_ms;

            // This keeps the highest ngroups if same values for multiple combinations
            if ((nf_diff < nf_diff_prev) || (frac < frac_prev))
            {
                ng_best = ng;
                nd_best = nd;
                nf_diff_prev = nf_diff;
                frac_prev = frac;
            }

            double tint = (double)ftime_ms * (ng * nr + (ng - 1) * nd);
            printf("ng: %i, nd: %i, nftot: %i, nftot_res: %i, nf_diff: %f, frac: %f, tint: %f\n",
                   ng, nd, nftot, nftot_res, nf_diff, frac, tint);

            if ((nf_diff <= 1) || (frac <= 0.05))
                break;
        }
        printf("ng_best: %i, nd_best: %i\n", ng_best, nd_best);
        ng = ng_best;
        nd = nd_best;
    }
    else
    {
        ng = nftot;
        nd = 0;
        nr = 1;
    }

    *ngroups = ng;
    *nreads = nr;
    *ndrops = nd;

    return true;
}

// Set exposure settings: nramps, ncoadds, ngroups, nreads, ndrops
// The number of ramps requested from the ASIC will be ncoadds*nsaved_ramps
bool set_exposure_settings(MACIE_Settings *ptUserData, bool bSave,
                           uint ncoadds, uint nsaved_ramps, uint ngroups, uint nreads, uint ndrops, uint nresets)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    ptUserData->bSaveData = bSave;

    if (ngroups < 1)
        ngroups = 1;
    if (nreads < 1)
        nreads = 1;
    if (nresets < 1)
        nresets = 1;

    if (ncoadds < 1)
        ncoadds = 1;
    if (nsaved_ramps < 1)
        nsaved_ramps = 1;

    ASIC_NCoadds(ptUserData, true, ncoadds);
    ASIC_NSaves(ptUserData, true, nsaved_ramps);

    verbose_printf(LOG_INFO, ptUserData, "Save data is currently %s\n", bSave ? "ENABLED" : "DISABLED");
    verbose_printf(LOG_INFO, ptUserData, "Number of coadds: %i\n", ncoadds);
    verbose_printf(LOG_INFO, ptUserData, "Number of saved ramps: %i\n", nsaved_ramps);

    ASIC_NRamps(ptUserData, true, ncoadds * nsaved_ramps);
    ASIC_NGroups(ptUserData, true, ngroups);
    ASIC_NReads(ptUserData, true, nreads);
    ASIC_NDrops(ptUserData, true, ndrops);
    ASIC_NResets(ptUserData, true, nresets);

    if (ReconfigureASIC(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Reconfigure failed at %s()\n", __func__);
        return false;
    }

    double rtime_ms = ptUserData->ramptime_ms;         // Ramp time including reset frames
    double itime_ms = exposure_inttime_ms(ptUserData); // Photon collection time
    double etime_sec = rtime_ms * ncoadds * nsaved_ramps / 1000;
    verbose_printf(LOG_INFO, ptUserData, "MACIE Clock Rate = %i MHz\n", ptUserData->clkRateM);
    verbose_printf(LOG_INFO, ptUserData, "Frame time: %.3f ms\n", ptUserData->frametime_ms);
    verbose_printf(LOG_INFO, ptUserData, "Ramp time: %.3f ms\n", rtime_ms);
    verbose_printf(LOG_INFO, ptUserData, "Ramp photon-collection time: %.3f ms\n", itime_ms);
    verbose_printf(LOG_INFO, ptUserData, "Estimated time to execute Exposure: %.3f sec\n", etime_sec);

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief set_frame_settings Set the window and stripe frame sizes.
/// \param ptUserData The user-set structure containing the hardware parameters.
/// \param bHorzWin Set horizontal window mode (if set, then window mode).
/// \param bVertWin Set vertical window mode (either window or stripe mode).
/// \param val Value output.
bool set_frame_settings(MACIE_Settings *ptUserData, bool bHorzWin, bool bVertWin,
                        uint x1, uint x2, uint y1, uint y2)
{

    unsigned int xdet = ptUserData->uiDetectorWidth;
    unsigned int ydet = ptUserData->uiDetectorHeight;

    // Fix values that are outside of detector bounds
    if (x1 > xdet - 1)
        x1 = 0;
    if (x2 > xdet - 1)
        x2 = xdet - 1;
    if (y1 > ydet - 1)
        y1 = 0;
    if (y2 > ydet - 1)
        y2 = ydet - 1;

    // Make sure x1 and y1 are not larger than x2 and y2, respectively
    if (y1 >= y2)
    {
        verbose_printf(LOG_WARNING, ptUserData, "%s(): y1=%i must be less than y2=%i. Setting y1=0.\n",
                       __func__, y1, y2);
        y1 = 0;
    }
    if (x1 >= x2)
    {
        verbose_printf(LOG_WARNING, ptUserData, "%s(): x1=%i must be less than x2=%i. Setting x1=0.\n",
                       __func__, x1, x2);
        x1 = 0;
    }

    // uint ny = y2 - y1 + 1;
    // uint nx = x2 - x1 + 1;

    // First check if we're trying to set Stripe Mode
    if ((bVertWin == true) && (bHorzWin == false))
    {
        // Enable stripe mode
        ASIC_STRIPEMode(ptUserData, true, true);

        // // TODO: For the meantime, we are restricted to powers of 2
        // if ((ny & (ny - 1)) != 0)
        // {
        //     verbose_printf(LOG_WARNING, ptUserData, "");
        // }
    }
    else
    {
        // Turn vertical window on/off first, then horizontal
        // Order matters, because ASIC_WinHorz will disable stripe
        ASIC_WinVert(ptUserData, true, (uint)bVertWin);
        ASIC_WinHorz(ptUserData, true, (uint)bHorzWin);
    }

    // Set y1=0 and y2=ydet-1 if bVertWin=False
    if (bVertWin == false)
    {
        y1 = 0;
        y2 = ydet - 1;
    }
    // Set x1=0 and x2=ydet-1 if bHorzWin=False
    if (bHorzWin == false)
    {
        x1 = 0;
        x2 = xdet - 1;
    }

    ASIC_setX1(ptUserData, x1);
    ASIC_setX2(ptUserData, x2);
    ASIC_setY1(ptUserData, y1);
    ASIC_setY2(ptUserData, y2);

    if (ReconfigureASIC(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Reconfigure failed at %s()\n", __func__);
        return false;
    }

    // TODO:
    // Pixel Clock scheme checks (i.e., Normal vs Enhanced) are necessary if there are
    // differences between full frame and subarray window clocking schemes. Normally
    // these would be the same, but there is a bug in the Slow Mode v5.0+ microcode
    // where Enhanced mode causes the columns to shift every other acquisition.
    // The shifted column then persists after switching back to full frame.
    // Something is wrong with the pixel timing code.
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    if (RegMap.count("PixelClkScheme") > 0)
    {
        uint pixClk = (bHorzWin == false) ? ptUserData->ffPixelClkScheme : ptUserData->winPixelClkScheme;
        SetASICParameter(ptUserData, "PixelClkScheme", pixClk);
        if (ReconfigureASIC(ptUserData) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "Reconfigure failed at %s()\n", __func__);
        }
    }

    x1 = ASIC_getX1(ptUserData);
    x2 = ASIC_getX2(ptUserData);
    y1 = ASIC_getY1(ptUserData);
    y2 = ASIC_getY2(ptUserData);
    // Get final xpix and ypix
    unsigned int xpix = exposure_xpix(ptUserData);
    unsigned int ypix = exposure_ypix(ptUserData);

    verbose_printf(LOG_INFO, ptUserData, "Horizontal Window: %i\n", ASIC_WinHorz(ptUserData, false, 0));
    verbose_printf(LOG_INFO, ptUserData, "  X1: %i X2: %i, xpix: %i\n", x1, x2, xpix);
    verbose_printf(LOG_INFO, ptUserData, "Vertical Window: %i\n", ASIC_WinVert(ptUserData, false, 0));
    verbose_printf(LOG_INFO, ptUserData, "  Y1: %i Y2: %i, ypix: %i\n", y1, y2, ypix);
    verbose_printf(LOG_INFO, ptUserData, "STRIPE Mode: %i\n", (uint)ASIC_STRIPEMode(ptUserData, false, false));
    verbose_printf(LOG_INFO, ptUserData, "Frame time: %.3f ms\n", ptUserData->frametime_ms);

    // If not full frame, check if subarray values and bytes requested are valid
    // TODO: This is temporary until MACIE data handling issue is resolved
    if ((bVertWin == true) || (bHorzWin == true))
    {
        // Number of bytes requested per ramp
        unsigned long framesize = (unsigned long)xpix * ypix;
        unsigned long nframes_ramp = (unsigned long)(ASIC_NReads(ptUserData, false, 0) * ASIC_NGroups(ptUserData, false, 0));
        unsigned long nbytes_ramp = 2 * nframes_ramp * framesize;
        if (verify_subarray_size(ptUserData, xpix, ypix, nbytes_ramp) == false)
        {
            verbose_printf(LOG_WARNING, ptUserData,
                           "%s(): Possible problematic subarray size (nx=%i, ny=%i) for %li bytes in ramp\n",
                           __func__, xpix, ypix, nbytes_ramp);
            // return false;
        }
    }

    return true;
}

// Subarray mode might not exist in certain microcodes.
// If these parameters don't exist, then return detector limits.
// If not in window mode, then return detector limits.

// Set/get STRIPE mode
bool ASIC_STRIPEMode(MACIE_Settings *ptUserData, bool bSet, bool bVal)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    map<string, regInfo> &RegMap = ptUserData->RegMap;

    // Check if we're turning Stripe Mode on/off
    if (bSet == true)
    {
        // If not allowed, then print warning and explicitly set bVal=false
        if ((ptUserData->bStripeModeAllowed == false) && (bVal == true))
        {
            verbose_printf(LOG_WARNING, ptUserData, "Stripe Mode is not allowed for current microcode.\n");
            verbose_printf(LOG_WARNING, ptUserData, "  Check ASIC Regs file: %s.\n", ptUserData->ASICRegs);
            bVal = false;
        }
        ptUserData->bStripeMode = bVal;

        // Enable/disable horizontal/vertical windows if enabling STRIPE
        if (bVal == true)
        {
            // Turn off Horizontal Window
            if (RegMap.count("WinMode") > 0)
                ASIC_Generic(ptUserData, "WinMode", true, 0);
            if (RegMap.count("HorzWinMode") > 0)
                ASIC_Generic(ptUserData, "HorzWinMode", true, 0);

            // Turn on Vertical Window
            if (RegMap.count("VertWinMode") > 0)
                ASIC_Generic(ptUserData, "VertWinMode", true, 1);
        }
        else if (ptUserData->bStripeModeAllowed)
        {
            // Turn off Vertical Window
            if (RegMap.count("VertWinMode") > 0)
                ASIC_Generic(ptUserData, "VertWinMode", true, 0);
            // Turn off any burst Striping
            if (RegMap.count("StripeReads1") > 0)
                ASIC_Generic(ptUserData, "StripeReads1", true, 0);
            if (RegMap.count("StripeReads2") > 0)
                ASIC_Generic(ptUserData, "StripeReads2", true, 0);
            if (RegMap.count("StripeSkips1") > 0)
                ASIC_Generic(ptUserData, "StripeSkips1", true, 0);
            if (RegMap.count("StripeSkips2") > 0)
                ASIC_Generic(ptUserData, "StripeSkips2", true, 0);
        }
    }
    else // Or simply get current state
    {
        // If not allowed, explicitly set bVal=false (no need for warning)
        if (ptUserData->bStripeModeAllowed == false)
            ptUserData->bStripeMode = false;

        bVal = ptUserData->bStripeMode;
    }

    return bVal;
}
// Horizontal Window
unsigned int ASIC_WinHorz(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    map<string, regInfo> &RegMap = ptUserData->RegMap;

    // Return 0 if Window Mode not possible
    string addr_name = "WinMode";
    if (RegMap.count(addr_name) == 0)
    {
        addr_name = "HorzWinMode";
        if (RegMap.count(addr_name) == 0)
            return 0;
    }

    // Disable STRIPE mode if we're enabling Horizontal Window
    if ((bSet == true) && (val > 0))
        ASIC_STRIPEMode(ptUserData, true, false);

    val = ASIC_Generic(ptUserData, addr_name, bSet, val);
    verbose_printf(LOG_DEBUG, ptUserData, "ASIC_WinHorz returns %i.\n", val);
    return val;
}
// Vertical Window
unsigned int ASIC_WinVert(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    map<string, regInfo> &RegMap = ptUserData->RegMap;

    bool bVal = (val == 0) ? false : true;
    // First check if we're en/disabling vertical window
    if (bSet == true)
    {
        // Set STRIPE mode if Horizontal Window Mode is false
        if ((ASIC_WinHorz(ptUserData, false, 0) == 0) && (ptUserData->bStripeModeAllowed))
        {
            ASIC_STRIPEMode(ptUserData, bSet, bVal);
            if (RegMap.count("VertWinMode") > 0)
                val = ASIC_Generic(ptUserData, "VertWinMode", bSet, val);
            else if ((RegMap.count("WinMode") == 0) && (bVal == false))
            {
                ASIC_setY1(ptUserData, 0);
                ASIC_setY2(ptUserData, ptUserData->uiDetectorHeight - 1);
            }
        }
        else if (RegMap.count("VertWinMode") > 0)
        {
            val = ASIC_Generic(ptUserData, "VertWinMode", bSet, val);
        }
        else if (RegMap.count("WinMode") > 0)
        {
            val = ASIC_Generic(ptUserData, "WinMode", bSet, val);
            verbose_printf(LOG_WARNING, ptUserData, "Setting WinMode=%i also controls Horizontal Window.\n", val);
        }
        else
        {
            val = 0;
        }
    }
    else
    {
        if (ASIC_STRIPEMode(ptUserData, bSet, bVal) == true)
            val = 1;
        else if (RegMap.count("VertWinMode") > 0)
            val = ASIC_Generic(ptUserData, "VertWinMode", bSet, val);
        else if (RegMap.count("WinMode") > 0)
            val = ASIC_Generic(ptUserData, "WinMode", bSet, val);
        else
            val = 0;
    }
    verbose_printf(LOG_DEBUG, ptUserData, "ASIC_WinVert returns %i.\n", val);

    return val;
}

// Get subarray starting position along x-axis
// If Horizontal Window is disabled, return 0
unsigned int ASIC_getX1(MACIE_Settings *ptUserData)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    unsigned int val = 0;

    if (ASIC_WinHorz(ptUserData, 0, 0) == false)
        val = 0;
    else if (RegMap.count("X1") > 0)
        val = ASIC_Generic(ptUserData, "X1", false, 0);
    else if (RegMap.count("XStart") > 0)
        val = ASIC_Generic(ptUserData, "XStart", false, 0);

    return val;
}
// Get subarray ending position along x-axis
// If Horizontal Window is disabled, return detector size
unsigned int ASIC_getX2(MACIE_Settings *ptUserData)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    unsigned int xdet = ptUserData->uiDetectorWidth;
    unsigned int val = xdet - 1;

    if (ASIC_WinHorz(ptUserData, 0, 0) == false)
        val = xdet - 1;
    else if (RegMap.count("X2") > 0)
        val = ASIC_Generic(ptUserData, "X2", false, 0);
    else if (RegMap.count("XSize") > 0)
        val = ASIC_getX1(ptUserData) + ASIC_Generic(ptUserData, "XSize", false, 0);

    return val;
}
unsigned int ASIC_getY1(MACIE_Settings *ptUserData)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    unsigned int val = 0;

    if (ASIC_WinVert(ptUserData, false, 0) == false)
        val = 0;
    else if (RegMap.count("Y1") > 0)
        val = ASIC_Generic(ptUserData, "Y1", false, 0);
    else if (RegMap.count("YStart") > 0)
        val = ASIC_Generic(ptUserData, "YStart", false, 0);

    return val;
}
unsigned int ASIC_getY2(MACIE_Settings *ptUserData)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    unsigned int ydet = ptUserData->uiDetectorHeight;
    unsigned int val = ydet - 1;

    if (ASIC_WinVert(ptUserData, false, 0) == false)
        val = ydet - 1;
    else if (RegMap.count("Y2") > 0)
        val = ASIC_Generic(ptUserData, "Y2", false, 0);
    else if (RegMap.count("YSize") > 0)
        val = ASIC_getY1(ptUserData) + ASIC_Generic(ptUserData, "YSize", false, 0) - 1;

    return val;
}

// Set subarray positions
// These functions only set the reg values and performs bounds checking.
// Will NOT enable Horizontal Window if it is disabled; use ASIC_WinHorz
// for that functionality.
unsigned int ASIC_setX1(MACIE_Settings *ptUserData, unsigned int val)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    unsigned int xdet = ptUserData->uiDetectorWidth;

    // Check if keys exist
    string addr_name = "X1";
    if (RegMap.count(addr_name) == 0)
    {
        addr_name = "XStart";
        if (RegMap.count(addr_name) == 0)
        {
            verbose_printf(LOG_WARNING, ptUserData, "Neither X1 nor XStart are valid register names.\n");
            return 0;
        }
    }

    // Valid range?
    if (val > xdet - 1)
    {
        verbose_printf(LOG_WARNING, ptUserData, "Value of %i is out of range. Valid values span 0 to %i.\n",
                       val, xdet - 1);
        val = 0;
    }

    verbose_printf(LOG_INFO, ptUserData, "Setting %s to %i.\n", addr_name.c_str(), val);
    return ASIC_Generic(ptUserData, addr_name, true, val);
}
unsigned int ASIC_setX2(MACIE_Settings *ptUserData, unsigned int val)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    unsigned int xdet = ptUserData->uiDetectorWidth;

    // Check if keys exist
    string addr_name = "X2";
    if (RegMap.count(addr_name) == 0)
    {
        addr_name = "XSize";
        if (RegMap.count(addr_name) == 0)
        {
            verbose_printf(LOG_WARNING, ptUserData, "Neither X2 nor XSize are valid register names.\n");
            return xdet - 1;
        }
    }

    if (val > xdet - 1)
    {
        verbose_printf(LOG_WARNING, ptUserData, "Value of %i is out of range. Valid values span 0 to %i.\n",
                       val, xdet - 1);
        val = xdet - 1;
    }

    if (addr_name == "XSize")
        val = val - ASIC_getX1(ptUserData) + 1;

    verbose_printf(LOG_INFO, ptUserData, "Setting %s to %i.\n", addr_name.c_str(), val);
    return ASIC_Generic(ptUserData, addr_name, true, val);
}
unsigned int ASIC_setY1(MACIE_Settings *ptUserData, unsigned int val)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    unsigned int ydet = ptUserData->uiDetectorHeight;

    // Check if keys exist
    string addr_name = "Y1";
    if (RegMap.count(addr_name) == 0)
    {
        addr_name = "YStart";
        if (RegMap.count(addr_name) == 0)
        {
            verbose_printf(LOG_WARNING, ptUserData, "Neither Y1 nor YStart are valid register names.\n");
            return 0;
        }
    }

    if (val > ydet - 1)
    {
        verbose_printf(LOG_WARNING, ptUserData, "Value of %i is out of range. Valid values span 0 to %i.\n",
                       val, ydet - 1);
        val = 0;
    }

    // If vertical window is off, then set to 0 if "VertWinMode" and "WinMode" don't exist
    if ((ASIC_WinVert(ptUserData, false, 0) == 0) &&
        (RegMap.count("VertWinMode") + RegMap.count("WinMode")) == 0)
    {
        val = 0;
    }
    verbose_printf(LOG_INFO, ptUserData, "Setting %s to %i.\n", addr_name.c_str(), val);
    return ASIC_Generic(ptUserData, addr_name, true, val);
}
unsigned int ASIC_setY2(MACIE_Settings *ptUserData, unsigned int val)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    unsigned int ydet = ptUserData->uiDetectorHeight;

    // Check if keys exist
    string addr_name = "Y2";
    if (RegMap.count(addr_name) == 0)
    {
        addr_name = "YSize";
        if (RegMap.count(addr_name) == 0)
        {
            verbose_printf(LOG_WARNING, ptUserData, "Neither Y2 nor YSize are valid register names.\n");
            return 0;
        }
    }

    if (val > ydet - 1)
    {
        verbose_printf(LOG_WARNING, ptUserData, "Value of %i is out of range. Valid values span 0 to %i.\n",
                       val, ydet - 1);
        val = ydet - 1;
    }

    // If vertical window is off, then set Y2=2047 if "VertWinMode" and "WinMode" don't exist
    if ((ASIC_WinVert(ptUserData, false, 0) == 0) &&
        (RegMap.count("VertWinMode") + RegMap.count("WinMode")) == 0)
    {
        val = ydet - 1;
    }

    if (addr_name == "YSize")
        val = val - ASIC_getY1(ptUserData) + 1;

    verbose_printf(LOG_INFO, ptUserData, "Setting %s to %i.\n", addr_name.c_str(), val);
    return ASIC_Generic(ptUserData, addr_name, true, val);
}

// Call this function to set burst mode to full frame for idling purposes (after acquisition)
void burst_stripe_set_ffidle(MACIE_Settings *ptUserData)
{

    map<string, regInfo> &RegMap = ptUserData->RegMap;
    unsigned int ydet = ptUserData->uiDetectorHeight;
    unsigned int ypix = 0;
    // If burst stripe mode is enabled,
    if (ypix_burst_stripe(ptUserData, &ypix, true) == true)
    {
        if (RegMap.count("StripeReads1") > 0)
            ASIC_Generic(ptUserData, "StripeReads1", true, 0);
        if (RegMap.count("StripeReads2") > 0)
            ASIC_Generic(ptUserData, "StripeReads2", true, 0);
        if (RegMap.count("StripeSkips1") > 0)
            ASIC_Generic(ptUserData, "StripeSkips1", true, 0);
        if (RegMap.count("StripeSkips2") > 0)
            ASIC_Generic(ptUserData, "StripeSkips2", true, 0);
        if (RegMap.count("RowReads") > 0)
            ASIC_Generic(ptUserData, "RowReads", true, ydet);
    }
}

// Returns true if running Burst Stripe Mode, otherwise false
bool ypix_burst_stripe(MACIE_Settings *ptUserData, unsigned int *ypix, bool bSet)
{
    map<string, regInfo> &RegMap = ptUserData->RegMap;

    unsigned int ydet = ptUserData->uiDetectorHeight;
    unsigned int y1 = ASIC_getY1(ptUserData);
    unsigned int y2 = ASIC_getY2(ptUserData);
    unsigned int ny = y2 - y1 + 1; // Number of requested rows

    // Set all to 0 if Stripe Mode is disabled or burst striping is not existent
    // or y1 and y2 cover the entire active region
    if ((ASIC_STRIPEMode(ptUserData, false, 0) == 0) || (RegMap.count("StripeReads1") == 0) || ((y1 < 4) && (y2 > ydet - 5)))
    {
        // Turn off any burst Striping
        if (bSet)
        {
            if (RegMap.count("StripeReads1") > 0)
                ASIC_Generic(ptUserData, "StripeReads1", true, 0);
            if (RegMap.count("StripeReads2") > 0)
                ASIC_Generic(ptUserData, "StripeReads2", true, 0);
            if (RegMap.count("StripeSkips1") > 0)
                ASIC_Generic(ptUserData, "StripeSkips1", true, 0);
            if (RegMap.count("StripeSkips2") > 0)
                ASIC_Generic(ptUserData, "StripeSkips2", true, 0);
            if (RegMap.count("RowReads") > 0)
                ASIC_Generic(ptUserData, "RowReads", true, ydet);
        }

        *ypix = ny;
        return false;
    }

    unsigned int yrows = 0;
    // If Stripe Mode is enabled and Burst Striping exists, update registers based on Y1 and Y2
    // We also want to always include the top/bottom reference rows
    if (y1 < 4) // Lower reference pixels included in active block
    {
        // yrows = ny + y1 + 4; // Number of requested rows plus bottom plus top
        yrows = ny;
        if (bSet)
        {
            ASIC_Generic(ptUserData, "StripeReads1", true, yrows - 4);
            ASIC_Generic(ptUserData, "StripeSkips1", true, ydet - yrows);
            ASIC_Generic(ptUserData, "StripeReads2", true, 4);
            ASIC_Generic(ptUserData, "StripeSkips2", true, 0);
            ASIC_Generic(ptUserData, "RowReads", true, yrows);
        }
    }
    else if (y2 > ydet - 5) // Upper reference pixels included in active block
    {
        // yrows = 4 + (ydet - y1); // Number of requested rows plus bottom plus top
        yrows = ny;
        if (bSet)
        {
            ASIC_Generic(ptUserData, "StripeReads1", true, 4);
            ASIC_Generic(ptUserData, "StripeSkips1", true, y1);
            ASIC_Generic(ptUserData, "StripeReads2", true, ydet - y1 - 4);
            ASIC_Generic(ptUserData, "StripeSkips2", true, 0);
            ASIC_Generic(ptUserData, "RowReads", true, yrows);
        }
    }
    else // No reference pixels included in requested block
    {
        // yrows = ny + 8;
        yrows = ny;
        if (bSet)
        {
            ASIC_Generic(ptUserData, "StripeReads1", true, 4);
            ASIC_Generic(ptUserData, "StripeSkips1", true, y1);
            ASIC_Generic(ptUserData, "StripeReads2", true, ny - 8);
            ASIC_Generic(ptUserData, "StripeSkips2", true, ydet - y2 - 1);
            ASIC_Generic(ptUserData, "RowReads", true, yrows);
        }
    }

    *ypix = yrows;
    return true;
}

unsigned int exposure_xpix(MACIE_Settings *ptUserData)
{
    return ASIC_getX2(ptUserData) - ASIC_getX1(ptUserData) + 1;
}
unsigned int exposure_ypix(MACIE_Settings *ptUserData)
{
    unsigned int ypix = 0;
    // Returns proper number BurstStripe is off or non-existent (Fast Mode)
    ypix_burst_stripe(ptUserData, &ypix, false);
    return ypix;
}

// Returns the frame time in terms of number of pixel times.
unsigned int exposure_frametime_pix(MACIE_Settings *ptUserData)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Update PixPerRow & RowsPerFrame for offline testing mode
    if (ptUserData->offline_develop == true)
    {
        LOG_LEVEL log_prev = get_verbose(ptUserData);
        set_verbose(ptUserData, LOG_WARNING);
        unsigned int nout = ASIC_NumOutputs(ptUserData);
        unsigned int xtra_pix = ASIC_Generic(ptUserData, "ExtraPixels", false, 0);
        unsigned int xtra_lines = ASIC_Generic(ptUserData, "ExtraLines", false, 0);
        unsigned int ppr = exposure_xpix(ptUserData) / nout + xtra_pix;
        unsigned int rpf = exposure_ypix(ptUserData) + xtra_lines;
        if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
            SetASICParameter(ptUserData, "PixPerRow", ppr + 8);
        else
            SetASICParameter(ptUserData, "PixPerRow", ppr);
        SetASICParameter(ptUserData, "RowsPerFrame", rpf + 1);
        set_verbose(ptUserData, log_prev);
    }

    unsigned int PixPerRow = 0;
    unsigned int RowsPerFrame = 0;
    unsigned int PixPerFrame = 0;

    // Get number of Pixels per Row
    if (GetASICParameter(ptUserData, "PixPerRow", &PixPerRow) == false)
        return 0;
    // Get number of Rows per Frame
    if (GetASICParameter(ptUserData, "RowsPerFrame", &RowsPerFrame) == false)
        return 0;

    PixPerFrame = PixPerRow * RowsPerFrame;

    return PixPerFrame;
}

// Time in msec to complete a frame
double exposure_frametime_ms(MACIE_Settings *ptUserData)
{
    double npix = (double)exposure_frametime_pix(ptUserData);

    // If in burst stripe mode, add in extra overhead for skipping rows
    double xtra_time = 0.0;
    unsigned int ypix = 0;
    unsigned int ydet = ptUserData->uiDetectorHeight;
    if (ypix_burst_stripe(ptUserData, &ypix, false) == true)
    {
        // 1.2 usec per skipped row at 100kHz
        // Should scale with pixel rate
        xtra_time = 0.0012 * (100. / double(ptUserData->pixelRate)) * (ydet - ypix);
    }

    // When in kHz, 1/f is msec
    return npix / ptUserData->pixelRate + xtra_time;
}

// Time in msec to complete a group
double exposure_grouptime_ms(MACIE_Settings *ptUserData)
{
    int nf_group = ASIC_NReads(ptUserData, false, 0) + ASIC_NDrops(ptUserData, false, 0);

    return nf_group * ptUserData->frametime_ms;
}

// Time in msec to complete a ramp (including resets)
double exposure_ramptime_ms(MACIE_Settings *ptUserData)
{
    int exp_nframe = (int)exposure_nframes(ptUserData, true);
    int nramps = (int)ASIC_NRamps(ptUserData, false, 0);

    return ptUserData->frametime_ms * (exp_nframe / nramps);
}

// On-sky integration (photon collection) time for a ramp
double exposure_inttime_ms(MACIE_Settings *ptUserData)
{
    int nresets = (int)ASIC_NResets(ptUserData, false, 0);
    return ptUserData->ramptime_ms - nresets * ptUserData->frametime_ms;
}

double exposure_efficiency(MACIE_Settings *ptUserData)
{

    unsigned int ui_ngroups = ASIC_NGroups(ptUserData, false, 0);
    unsigned int ui_nreads = ASIC_NReads(ptUserData, false, 0);
    unsigned int ui_nresets = ASIC_NResets(ptUserData, false, 0);

    if ((ui_ngroups == 1) && (ui_nreads == 1))
    {
        return 1.0 / double(1 + ui_nresets);
    }
    else
    {
        double itime = exposure_inttime_ms(ptUserData) - ptUserData->frametime_ms;
        return itime / ptUserData->ramptime_ms;
    }
}

// Return number of outputs for given detector configuration (science frames)
unsigned int ASIC_NumOutputs(MACIE_Settings *ptUserData)
{
    // Default to return nout=1 if subarray, else NumOutputs reg value
    return ASIC_NumOutputs(ptUserData, false);
}
// Return number of configured outputs for given detector configuration
// bFullFrame is used for determing full frame NOuts in case window mode is enabled
unsigned int ASIC_NumOutputs(MACIE_Settings *ptUserData, bool bFullFrame)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    unsigned int nout = 0;
    // Slow Mode values are stored in "NumOutputs"
    if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
    {
        // If Horizontal Window is enabled, only 1 output
        if ((ASIC_WinHorz(ptUserData, false, 0) == 1) && (bFullFrame == false))
            nout = 1;
        else
            GetASICParameter(ptUserData, "NumOutputs", &nout);
    }
    // Fast Mode outputs are either 16 (H1RG) or 32 (H2/4RG)
    else
    {
        nout = ptUserData->DetectorType == CAMERA_TYPE_H1RG ? 16 : 32;
    }

    return nout;
}
// Overloaded version of above for setting (and getting) NumOutputs
unsigned int ASIC_NumOutputs(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{

    if (bSet == false)
    {
        val = ASIC_NumOutputs(ptUserData);
        verbose_printf(LOG_INFO, ptUserData, "NumOutputs = %i\n", val);
        return val;
    }
    else
    {
        if (SettingsCheckNULL(ptUserData) == false)
            return false;

        // Slow Mode values are stored in "NumOutputs" keyword
        if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
        {
            unsigned int uiDetType = 0;
            GetASICParameter(ptUserData, "DetectorType", &uiDetType);

            // If Horizontal Window is enabled, only 1 output
            if (ASIC_WinHorz(ptUserData, false, 0) == 1)
            {
                verbose_printf(LOG_INFO, ptUserData, "Horizontal Window mode enabled. NumOutputs=1\n");
                val = 1;
            }
            else if (uiDetType == 1)
            {
                // Values can either be 1, 2, or 16
                if ((val != 1) && (val != 2) && (val != 16))
                {
                    val = 2;
                    verbose_printf(LOG_ERROR, ptUserData,
                                   "DetType=%i. NumOutputs can either be 1, 2, or 16. Setting to default of %i\n",
                                   uiDetType, val);
                }
            }
            else if (uiDetType == 2)
            {
                // Values can either be 1, 4, or 32
                if ((val != 1) && (val != 4) && (val != 32))
                {
                    // GetASICParameter(ptUserData, "NumOutputs", &val);
                    val = 4;
                    verbose_printf(LOG_ERROR, ptUserData,
                                   "DetType=%i. NumOutputs can either be 1, 4, or 32. Setting to default of%i\n",
                                   uiDetType, val);
                }
            }
            else if (uiDetType == 4)
            {
                // Values can either be 1, 4, 16, or 32
                if ((val != 1) && (val != 4) && (val != 16) && (val != 32))
                {
                    val = 2;
                    verbose_printf(LOG_ERROR, ptUserData,
                                   "DetType=%i. NumOutputs can either be 1, 4, 16, or 32. Setting to default of%i\n",
                                   uiDetType, val);
                }
            }
            SetASICParameter(ptUserData, "NumOutputs", val);
        }
        // Fast Mode outputs are either 16 (H1RG) or 32 (H2/4RG)
        else
        {
            val = ASIC_NumOutputs(ptUserData);
            // GetASICParameter(ptUserData, "NumOutputs", &val);
            verbose_printf(LOG_INFO, ptUserData, "NumOutputs is always fixed for Fast Mode. Staying at %i\n", val);
        }
    }
    return val;
}

////////////////////////////////////////////////////////////////////////////////
// Preamp Gain (dB)
// Cap Comp (fF)
// Filter Pole (kHz)
unsigned int ASIC_Gain(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Check if addr_name key exists
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    string addr_name = "Gain";

    if (RegMap.count(addr_name) == 0)
    {
        unsigned int addr = 0x6101;
        struct regInfo *reg = new regInfo;
        reg->addr = addr;
        reg->bit0 = 0;
        reg->bit1 = 3;
        reg->value = val;

        // If Gain keyword doesn't exist, then there is no shadow register
        // so we need to get/set Gain regs (6101, 6105, etc.) directly
        unsigned int nout = ASIC_NumOutputs(ptUserData, true);
        if (bSet == true)
        {
            for (unsigned int i = 0; i < nout; ++i)
            {
                reg->addr = addr + 4 * i;
                // printf("h%04x, %i-%i, %i\n", reg->addr, reg->bit0, reg->bit1, reg->value);
                WriteASICBits(ptUserData, reg);
            }
        }
        ReadASICBits(ptUserData, reg, &val);
    }
    else
    {
        val = ASIC_Generic(ptUserData, addr_name, bSet, val);
    }

    int gain_db[16] = {-3, 0, 3, 6, 6, 9, 9, 12, 12, 15, 15, 18, 18, 21, 24, 27};
    int val_db = gain_db[val];

    verbose_printf(LOG_INFO, ptUserData, "Gain = %i (%i db)\n", val, val_db);
    return val;
}

// Recommended values in Table 3-10 of SIDECAR Manual
// Val should be 0 to 63.
unsigned int ASIC_CapComp(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Check if addr_name key exists
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    string addr_name = "CapComp";

    // unsigned int nbits = 0;
    // If CapComp doesn't exist as a shadow register,
    // then we need to set register directly
    if (RegMap.count(addr_name) == 0)
    {
        unsigned int addr = 0x6101;
        struct regInfo *reg = new regInfo;
        reg->addr = addr;
        reg->bit0 = 4;
        reg->bit1 = 9;
        reg->value = val;

        // If keyword doesn't exist, then there is no shadow register
        // so we need to get/set regs (6101, 6105, etc.) directly
        unsigned int nout = ASIC_NumOutputs(ptUserData, true);
        if (bSet == true)
        {
            for (unsigned int i = 0; i < nout; ++i)
            {
                reg->addr = addr + 4 * i;
                WriteASICBits(ptUserData, reg);
            }
        }
        ReadASICBits(ptUserData, reg, &val);
        // nbits = reg->bit1 - reg->bit0 + 1;
    }
    else
    {
        val = ASIC_Generic(ptUserData, addr_name, bSet, val);
        // nbits = RegMap[addr_name].bit1 - RegMap[addr_name].bit0 + 1;
    }

    unsigned int val_fF = 53 * val;
    // for (unsigned int i = 0; i < nbits; ++i)
    //     val_fF += ((val >> i) & 1) * 53 * uint(pow(2, i));
    verbose_printf(LOG_INFO, ptUserData, "CapComp = %i (%i fF)\n", val, val_fF);

    return val;
}

// Set filter pole to 5-10 times the pixel clock rate
unsigned int ASIC_FiltPole(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Check if addr_name key exists
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    string addr_name = "FiltPole";

    // If keyword doesn't exist, then there is no shadow register
    // so we need to get/set regs (6102, 6106, etc.) directly
    if (RegMap.count(addr_name) == 0)
    {
        unsigned int addr = 0x6102;
        struct regInfo *reg = new regInfo;
        reg->addr = addr;
        reg->bit0 = 12;
        reg->bit1 = 15;
        reg->value = val;

        unsigned int nout = ASIC_NumOutputs(ptUserData, true);
        if (bSet == true)
        {
            for (unsigned int i = 0; i < nout; ++i)
            {
                reg->addr = addr + 4 * i;
                WriteASICBits(ptUserData, reg);
            }
        }
        ReadASICBits(ptUserData, reg, &val);
    }
    else
    {
        val = ASIC_Generic(ptUserData, addr_name, bSet, val);
    }

    int khz_fast[16] = {265392, 15165, 7582, 5055, 3791, 2527, 1895,
                        1263, 947, 669, 465, 334, 232, 164, 116, 82};
    int khz_slow[16] = {132696, 7582, 3791, 2527, 1895, 1263, 947, 631,
                        473, 392, 272, 196, 136, 109, 86, 65};
    int val_kHz = ptUserData->DetectorMode == CAMERA_MODE_SLOW ? khz_slow[val] : khz_fast[val];

    verbose_printf(LOG_INFO, ptUserData, "FiltPole = %i (%i kHz)\n", val, val_kHz);
    return val;
}

// Set ASIC inputs (ie., single-ended, differential, grounded) directly using the override reg.
// val should be a 16-bit HEX value like 0xaaaa that eventually propogates to h6100, etc.
// There are three possible implementations depending on detector and mode.
//   1. If RefInput does not exist, then we're in Fast Mode and need to directly set h6100, etc.
//   2. Otherwise, we're using he HxRG ucode, so set RefOverride=1 and set h5100=val.
unsigned int ASIC_Inputs(MACIE_Settings *ptUserData, bool bSet, unsigned int val)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Check if addr_name key exists
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    if (RegMap.count("RefInput") == 0)
    {
        // Fast Mode with 16/32 channels
        unsigned int addr = 0x6100;
        struct regInfo *reg = new regInfo;
        reg->addr = addr;
        reg->bit0 = 0;
        reg->bit1 = 15;
        reg->value = val;

        unsigned int nout = ASIC_NumOutputs(ptUserData, true);
        if (bSet == true)
        {
            for (unsigned int i = 0; i < nout; ++i)
            {
                reg->addr = addr + 4 * i;
                WriteASICBits(ptUserData, reg);
            }
        }
        ReadASICBits(ptUserData, reg, &val);
    }
    else if (RegMap.count("RefOverride") == 0)
    {
        // JWST Mode (ie., no RefOverride)
        // If bSet is false, then this will output the value of h433a or h433b
        // depending on the current RefInput setting.
        // If bSet is true, then we set RefInput=1 to tell ucode to grab
        // setting from h433b, then we modify h433b
        if (ASIC_Generic(ptUserData, "RefInput", bSet, 1) == 0)
            val = ASIC_Generic(ptUserData, "SingValue", bSet, val);
        else
            val = ASIC_Generic(ptUserData, "DiffValue", bSet, val);
    }
    else
    {
        unsigned int sing_val = ASIC_Generic(ptUserData, "NumChAvg", false, 0) == 1 ? 0x4a0a : 0x4aca;
        unsigned int diff_val = ASIC_Generic(ptUserData, "NumChAvg", false, 0) == 1 ? 0x4502 : 0x45c2;

        // HxRG microcode
        // If bSet is true, then set RefOverride, set OverrideVals, and return OverrideVals in h5100
        // If bSet is false, but RefOverride==1, then return OverrideVals in h5100
        // Otherwise, return single or differential values (bSet should then be false).
        if (ASIC_Generic(ptUserData, "RefOverride", bSet, 1) == 1)
            val = ASIC_Generic(ptUserData, "OverrideVals", bSet, val);
        else
            val = ASIC_Generic(ptUserData, "RefInput", false, 0) == 0 ? sing_val : diff_val;
    }

    verbose_printf(LOG_INFO, ptUserData, "Ref Inputs = 0x%04x\n", val);
    return val;
}

// DAC Setting consists of bits 0-10
// Bit 0-9 give the Voltage
// Bit 10 sets the low/high range (0-2V or 1.3-3.3V)
float ConvertDACToV(unsigned int dac_setting)
{
    // unsigned int nbits = reg->bit1 - reg->bit0 + 1;
    // *val >>= reg->bit0;                // Shift val bits to the right
    // *val &= (1 << nbits) - 1;          // Bitwise AND with a bitmask

    // AND with bitmask to get voltage
    unsigned int bitmask = (1 << 10) - 1;
    unsigned int reg_voltage = dac_setting & bitmask;
    // Shift and AND to get range
    unsigned int reg_range = (dac_setting >> 10) & 1;

    return (float)2 * reg_voltage / 1023 + 1.3 * reg_range;
}

unsigned int ConvertVToDAC(float volts)
{
    unsigned int value = 0;
    if (volts < 2)
        value = (uint)ceil(1023 * (volts / 2.0));
    else
    {
        value = (uint)ceil(1023 * ((volts - 1.3) / 2.0));
        value |= (1 << 10);
    }

    return value;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief readASICconfig Given a start address and number of registers,
///  decdode the register configurations to voltages, CapComp, DACBuff, current, etc.
///  All data is printed to the terminal output.
/// \param ptUserData The user-set structure containing hardware parameters
/// \param addr Start register address
/// \param nreg Number of registers to decode
bool readASICconfig(MACIE_Settings *ptUserData, unsigned short addr, int nreg)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    uint val_arr[nreg] = {};
    if (ReadASICBlock(ptUserData, addr, nreg, &val_arr[0]) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "ReadASICBlock failed in %s\n", __func__);
        return false;
    }

    uint uiDACrange, uiDACvolt, uiDACPwrDwn, uiCapComp, uiDACbuff;
    float flDACvolt = 0;
    float flDACbuff = 0;

    uint uiCurrFine, uiCurrCoarse, uiISinkEn, uiCurrPwrDwn;
    float flCurr_uA = 0;

    uint uiAddr, uiVal;
    for (int i = 0; i < nreg; i++)
    {
        uiAddr = (uint)addr + i;
        uiVal = val_arr[i];
        // Voltage Config addresses
        if ((uiAddr % 2 == 0) && (uiAddr >= 0x6000) && (uiAddr <= 0x6037))
        {
            // Check if powered
            uiDACPwrDwn = (uiVal >> 11) & 1;

            // Get Capacitor Compensation
            uiCapComp = (uiVal >> 12) & 3;

            // Calculate DAC Voltage
            uiDACrange = (uiVal >> 10) & 1;
            uiDACvolt = uiVal & ((1 << 10) - 1);
            flDACvolt = (float)2 * uiDACvolt / 1023 + 1.3 * uiDACrange;

            // Calculate DAC buffer stored in next register
            regInfo regDACbuff = gen_regInfo((ushort)uiAddr + 1, 10, 15, 0);
            ReadASICBits(ptUserData, &regDACbuff, &uiDACbuff);
            flDACbuff = 60 * pow(pow(10, -1.421 / 20), 63 - uiDACbuff);

            printf("  0x%04x = 0x%04x (%5.3f V; DACPwr %s); CapComp = %i; DACBuff = %6.3f mA\n",
                   uiAddr, uiVal, flDACvolt, uiDACPwrDwn == 1 ? "OFF" : "ON", uiCapComp, flDACbuff);
        }
        // Current Config addresses
        else if ((uiAddr % 2 == 1) && (uiAddr >= 0x6000) && (uiAddr <= 0x6037))
        {
            // Get fine and coarse current settings
            uiCurrFine = uiVal & ((1 << 8) - 1);
            uiCurrCoarse = (uiVal >> 8) & 3;

            flCurr_uA = (float)0.1 * (uiCurrFine + 1) * pow(10, uiCurrCoarse);

            // Get current source PwrDwn bit and ISinkEn bit from previous address
            regInfo regPrev = gen_regInfo((ushort)uiAddr - 1, 15, 15, 0);
            ReadASICBits(ptUserData, &regPrev, &uiCurrPwrDwn);
            regPrev.bit0 = 14;
            regPrev.bit1 = 14;
            ReadASICBits(ptUserData, &regPrev, &uiISinkEn);

            printf("  0x%04x = 0x%04x (%7.1f uA; CurrPwr %s); ISinkEn: %s\n",
                   uiAddr, uiVal, flCurr_uA, uiCurrPwrDwn == 1 ? "OFF" : "ON", uiISinkEn == 1 ? "Sink" : "Source");
        }
        // Internal Bias Currents 8-16
        else if ((uiAddr >= 0x6038) && (uiAddr <= 0x603b))
        {
            regInfo regVals = gen_regInfo((ushort)uiAddr, 0, 0, 0);

            uint uiVal1 = uiVal & ((1 << 8) - 1);
            uint uiVal2 = uiVal >> 8;

            ////////////////////////////////
            // First current (bits 0-7)
            uiCurrFine = uiVal1;

            // Coarse selection
            regVals.addr = 0x603c;
            regVals.bit0 = 4 * (uiAddr - 0x6038);
            regVals.bit1 = regVals.bit0 + 1;
            ReadASICBits(ptUserData, &regVals, &uiCurrCoarse);

            flCurr_uA = (float)0.1 * (uiCurrFine + 1) * pow(10, uiCurrCoarse);

            // Get current source PwrDwn bit and ISinkEn bit from previous address
            regVals.addr = 0x603d;
            regVals.bit0 = 2 * (uiAddr - 0x6038);
            regVals.bit1 = regVals.bit0;
            ReadASICBits(ptUserData, &regVals, &uiISinkEn);
            regVals.bit0 += 8; // Shift to top 8 bits
            regVals.bit1 = regVals.bit0;
            ReadASICBits(ptUserData, &regVals, &uiCurrPwrDwn);

            printf("  0x%04x<7-0>  = 0x%04x (%7.1f uA; CurrPwr %s); ISinkEn: %s\n",
                   uiAddr, uiVal1, flCurr_uA, uiCurrPwrDwn == 1 ? "OFF" : "ON", uiISinkEn == 1 ? "Sink" : "Source");

            ////////////////////////////////
            // Second current (bits 8-15)
            uiCurrFine = uiVal2;

            // Coarse selection
            regVals.addr = 0x603c;
            regVals.bit0 = 4 * (uiAddr - 0x6038) + 2;
            regVals.bit1 = regVals.bit0 + 1;
            ReadASICBits(ptUserData, &regVals, &uiCurrCoarse);

            flCurr_uA = (float)0.1 * (uiCurrFine + 1) * pow(10, uiCurrCoarse);

            // Get current source PwrDwn bit and ISinkEn bit from previous address
            regVals.addr = 0x603d;
            regVals.bit0 = 2 * (uiAddr - 0x6038) + 1;
            regVals.bit1 = regVals.bit0;
            ReadASICBits(ptUserData, &regVals, &uiISinkEn);
            regVals.bit0 += 8;
            regVals.bit1 = regVals.bit0;
            ReadASICBits(ptUserData, &regVals, &uiCurrPwrDwn);

            printf("  0x%04x<15-8> = 0x%04x (%7.1f uA; CurrPwr %s); ISinkEn: %s\n",
                   uiAddr, uiVal2, flCurr_uA, uiCurrPwrDwn == 1 ? "OFF" : "ON", uiISinkEn == 1 ? "Sink" : "Source");
        }
        else
        {
            printf(" Cannot calculate values for register h%04x\n", uiAddr);
        }
    }

    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief ASIC_VReadBack Perform voltage/current telemetry readack on the ASIC.
///  Refer to Table 3.3 in the ASIC Manual for details. For instance, to readback
///  register h6000, set mux_index to 0.
/// \param ptUserData The user-set structure containing all the parameters
/// for the hardware.
/// \param mux_index Which register to readback. Values [0-63]
/// \param val_h7000 Output for h7000 register (current)
/// \param val_h7400 Output for h7400 register (voltage)
bool ASIC_VReadBack(MACIE_Settings *ptUserData, unsigned int mux_index,
                    unsigned int *val_h7000, unsigned int *val_h7400)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Update h6192 to reroute voltage, current, and digital signals to
    // preamps for digitization.
    struct regInfo *reg = new regInfo;
    *reg = gen_regInfo(0x6192, 10, 15, mux_index);
    unsigned int val_orig = 0;

    // Store current values in val_origi
    if (ReadASICReg(ptUserData, reg->addr, &val_orig) == false)
        return false;

    // Write new values
    if (WriteASICBits(ptUserData, reg) == false)
        return false;

    // Delay 100 msec
    delay(100);

    // Return to original value after reading
    reg->value = val_orig;

    if (ReadASICReg(ptUserData, 0x7000, val_h7000) == false)
    {
        WriteASICBits(ptUserData, reg);
        return false;
    }
    if (ReadASICReg(ptUserData, 0x7400, val_h7400) == false)
    {
        WriteASICBits(ptUserData, reg);
        return false;
    }

    WriteASICBits(ptUserData, reg);
    return true;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief verbose_printf Prints out messages based on a 'level' to
/// stderr. The level requested is specified by calling 'isdec_set_verbose'.
/// If the level requested here is greater than or equal to the level set by
/// the user, the message will be printed.
/// \param level The verbosity level this message has.
/// \param ptUserData The user-set structure containing all the parameters
/// for the hardware.
/// \param format A string using a printf-like format to print out the string.
void verbose_printf(LOG_LEVEL level, MACIE_Settings *ptUserData, const char *format, ...)
{
    if (get_verbose(ptUserData) <= level)
    {
        if (level != LOG_NONE)
            fprintf(stderr, "[%5s] ", convert_log_type_str(level));

        va_list arg;
        va_start(arg, format);
        vfprintf(stderr, format, arg);
        va_end(arg);
    }
}

////////////////////////////////////////////////////////////////////////////////
/// \brief set_verbose Sets the verbosity requested by the user. This
/// value is stored in the MACIE_Settings struct. If the struct is NULL,
/// nothing is changed.
/// \param ptUserData The user-set structure containing all the parameters
/// for the hardware.
/// \param level The level of verbosity requested by the user.
//    LOG_DEBUG, LOG_INFO, LOG_WARNING, LOG_ERROR, LOG_NONE

void set_verbose(MACIE_Settings *ptUserData, LOG_LEVEL level)
{
    // Is our structure ok?
    if (SettingsCheckNULL(ptUserData) == true)
        ptUserData->verbosity = level;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief get_verbose Gets the verbosity set by the user and stored in
/// the MACIE_Settings struct. If the struct is NULL, 0 is returned by default.
/// \param ptUserData The user-set structure containing all the parameters
/// for the hardware.
/// \return The verbosity level set, or LOG_NONE if ptUserData is invalid.
LOG_LEVEL get_verbose(MACIE_Settings *ptUserData)
{
    // Is our structure ok?
    if (SettingsCheckNULL(ptUserData) == true)
        return ptUserData->verbosity;
    else
        return LOG_NONE;
}

////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////

string strip_white(const string &input)
{
    size_t b = input.find_first_not_of(' ');
    if (b == string::npos)
        b = 0;
    return input.substr(b, input.find_last_not_of(' ') + 1 - b);
}

string strip_comments(const string &input, const string &delimiters)
{
    return strip_white(input.substr(0, input.find_first_of(delimiters)));
}

// Quick function to create register info in a RegMap
regInfo gen_regInfo(unsigned short addr, unsigned short bit0, unsigned short bit1,
                    unsigned int value)
{
    regInfo reg = {addr, bit0, bit1, value};
    return reg;
}

// Given a Detector type and Readout mode, return a mapped dictionary
// of the register addresses, bits, and values.
// This reads the *.cfg files that correspond to the .mcd microcode files.
// For this initializaton phase, all reg values are set to 0.
bool initRegMap(MACIE_Settings *ptUserData)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Create variable that points to ptUserData->RegMap
    map<string, regInfo> &RegMap = ptUserData->RegMap;
    RegMap.clear();

    std::ifstream regs_file(ptUserData->ASICRegs);
    if (regs_file.is_open())
    {
        unsigned int linecount = 0;
        const string whitespace(" \t\n\r");
        const string delimiters("#/;");
        string linebuffer;

        string addr_name, addr_str;
        unsigned short addr;
        unsigned short bit0;
        unsigned short bit1;

        // vector<string> results;

        while (getline(regs_file, linebuffer))
        {
            size_t first_nonws = linebuffer.find_first_not_of(whitespace);

            // skip empty lines
            if (first_nonws == string::npos)
            {
                continue;
            }
            // skip comment lines
            if ((linebuffer.find("/") == first_nonws) ||
                (linebuffer.find("#") == first_nonws) ||
                (linebuffer.find(";") == first_nonws))
            {
                continue;
            }

            // Remove comments from end of line
            linebuffer = strip_comments(linebuffer, delimiters);

            // Make string stream
            std::istringstream iss(linebuffer);

            // Stream to reg name, address, bit0, and bit1
            iss >> addr_name >> addr_str >> bit0 >> bit1;
            // Convert HEX string to unsigned short
            addr = strtoul(addr_str.c_str(), 0, 16);

            // if (addr_name == "StripeAllowed") // Special case
            if (addr_name.compare("StripeAllowed") == 0)
                ptUserData->bStripeModeAllowed = bit1 == 0 ? false : true;
            else
                RegMap[addr_name] = gen_regInfo(addr, bit0, bit1, 0);

            ++linecount;
        }
    }
    else
    {
        verbose_printf(LOG_ERROR, ptUserData, "Could not open file %s\n", ptUserData->ASICRegs);
        return false;
    }

    // map<string, regInfo> RegMap = ptUserData->RegMap;
    map<string, regInfo>::iterator it;
    regInfo *reg;

    for (it = RegMap.begin(); it != RegMap.end(); it++)
    {
        reg = &it->second;
        verbose_printf(LOG_DEBUG, ptUserData, "%s : h%04x <%i:%i> = %i\n",
                       it->first.c_str(), reg->addr, reg->bit1, reg->bit0, reg->value);
    }
    return true;
}

const char *convert_camera_type_str(CAMERA_TYPE type)
{
    if (type == CAMERA_TYPE_H1RG)
        return "H1RG";
    else if (type == CAMERA_TYPE_H2RG)
        return "H2RG";
    else if (type == CAMERA_TYPE_H4RG)
        return "H4RG";

    return "UNKNOWN";
}

CAMERA_TYPE convert_camera_type(const char *pcDetectorType)
{
    if (strcmp(pcDetectorType, "H1RG") == 0)
        return CAMERA_TYPE_H1RG;
    else if (strcmp(pcDetectorType, "H2RG") == 0)
        return CAMERA_TYPE_H2RG;
    else if (strcmp(pcDetectorType, "H4RG") == 0)
        return CAMERA_TYPE_H4RG;

    return CAMERA_TYPE_H2RG;
}

const char *convert_camera_mode_str(CAMERA_MODE mode)
{
    if (mode == CAMERA_MODE_SLOW)
        return "SLOW";
    else if (mode == CAMERA_MODE_FAST)
        return "FAST";

    return "UNKNOWN";
}

CAMERA_MODE convert_camera_mode(const char *pcDetectorMode)
{
    if (strcmp(pcDetectorMode, "SLOW") == 0)
        return CAMERA_MODE_SLOW;
    else if (strcmp(pcDetectorMode, "FAST") == 0)
        return CAMERA_MODE_FAST;

    return CAMERA_MODE_SLOW;
}

const char *convert_log_type_str(LOG_LEVEL level)
{
    if (level == LOG_DEBUG)
        return "DEBUG";
    else if (level == LOG_INFO)
        return "INFO";
    else if (level == LOG_WARNING)
        return "WARN";
    else if (level == LOG_ERROR)
        return "ERROR";
    else if (level == LOG_NONE)
        return "NONE";

    return "UNKNOWN";
}

LOG_LEVEL convert_log_type(const char *pcLevel)
{
    if (strcmp(pcLevel, "DEBUG") == 0)
        return LOG_DEBUG;
    else if (strcmp(pcLevel, "INFO") == 0)
        return LOG_INFO;
    else if (strcmp(pcLevel, "WARN") == 0)
        return LOG_WARNING;
    else if (strcmp(pcLevel, "ERROR") == 0)
        return LOG_ERROR;
    else if (strcmp(pcLevel, "NONE") == 0)
        return LOG_NONE;

    return LOG_NONE;
}

////////////////////////////////////////////////////////////////////////////////

// Given a Detector type and Readout mode, return a mapped dictionary
// of the register addresses, bits, and values.
// This reads the *.cfg files that correspond to the .mcd microcode files.
// For this initializaton phase, all reg values are set to 0.
// Only used for testing when no hardware is connected.
bool initASICRegs_testing(MACIE_Settings *ptUserData)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    // Create variable that points to ptUserData->RegMap
    map<string, regInfo> &RegMap = ptUserData->RegAllASIC;
    RegMap.clear();

    std::ifstream regs_file(ptUserData->ASICFile);
    if (regs_file.is_open())
    {
        unsigned int linecount = 0;
        const string whitespace(" \t\n\r");
        const string delimiters("#/;");
        string linebuffer;

        string addr_str, value_str;
        unsigned short addr, value;

        // vector<string> results;

        while (getline(regs_file, linebuffer))
        {
            size_t first_nonws = linebuffer.find_first_not_of(whitespace);

            // skip empty lines
            if (first_nonws == string::npos)
            {
                continue;
            }
            // skip comment lines
            if ((linebuffer.find("/") == first_nonws) ||
                (linebuffer.find("#") == first_nonws) ||
                (linebuffer.find(";") == first_nonws))
            {
                continue;
            }

            // Remove comments from end of line
            linebuffer = strip_comments(linebuffer, delimiters);

            // Make string stream
            std::istringstream iss(linebuffer);

            // Stream to reg name, address, bit0, and bit1
            // iss >> addr_name >> addr_str >> bit0 >> bit1;
            iss >> addr_str >> value_str;
            addr_str.insert(0, "0x");
            value_str.insert(0, "0x");

            if ((addr_str.length() == 6) && (value_str.length() == 6))
            {
                // Convert HEX strings to unsigned short
                addr = strtoul(addr_str.c_str(), 0, 16);
                value = strtoul(value_str.c_str(), 0, 16);
                RegMap[addr_str] = gen_regInfo(addr, 0, 15, value);
            }

            ++linecount;
        }
    }
    else
    {
        verbose_printf(LOG_ERROR, ptUserData, "Could not open file %s\n", ptUserData->ASICFile);
        return false;
    }

    // map<string, regInfo> RegMap = ptUserData->RegMap;
    map<string, regInfo>::iterator it;
    regInfo *reg;

    for (it = RegMap.begin(); it != RegMap.end(); it++)
    {
        reg = &it->second;
        verbose_printf(LOG_DEBUG, ptUserData, "%s : h%04x = 0x%04x\n",
                       it->first.c_str(), reg->addr, reg->value);
    }
    return true;
}
