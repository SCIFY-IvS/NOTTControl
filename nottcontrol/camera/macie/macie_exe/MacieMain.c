// Macie_exe.c
////////////////////////////////////////////////////////////////////////////////
//
// Copyright 2019, Jarron Leisenring, All rights reserved.
//

#include "macie_lib.h"

#include <errno.h>
#include <getopt.h>
#include <algorithm>

#include <readline/readline.h>
#include <readline/history.h>

#include <fstream>
#include <iostream>

// #ifndef FALSE
// #define FALSE 0
// #endif
// #ifndef TRUE
// #define TRUE (!(FALSE))
// #endif

#include <bitset>
// using namespace std;
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

// Run an ASIC Tuning file
bool run_asic_tune_file(string tuneFile, MACIE_Settings *ptUserData);

// Testing buffere allocation function
bool test_buff_config(MACIE_Settings *ptUserData, int buffsize, short nbuf);

// Function to parse camera/mode-specific config file and load settings
bool ParseConfig(string configFile, MACIE_Settings *ptUserData, bool update_regs);

// Function to initialize MACIE/ASIC/Detector
bool InitCamera(string configFile, MACIE_Connection connection, MACIE_Settings *ptUserData);

// Free up resources
bool free_resources(MACIE_Settings *ptUserData);

// returns number of words in char string
unsigned int countWords(char *str);

// Test if string is HEX or decimal by presence of "0x"
unsigned int str2uint(string option);

// Class to parse command line input
class InputParser
{
public:
    InputParser(int &argc, char **argv)
    {
        for (int i = 1; i < argc; ++i)
            this->tokens.push_back(std::string(argv[i]));
    }
    const std::string &getCmdOption(const std::string &option) const
    {
        std::vector<std::string>::const_iterator itr;
        itr = std::find(this->tokens.begin(), this->tokens.end(), option);
        if (itr != this->tokens.end() && ++itr != this->tokens.end())
        {
            return *itr;
        }
        static const std::string empty_string("");
        return empty_string;
    }
    bool cmdOptionExists(const std::string &option) const
    {
        return std::find(this->tokens.begin(), this->tokens.end(), option) != this->tokens.end();
    }

private:
    std::vector<std::string> tokens;
};

///////////////////////////////////////////////////
// Tab completion from:
//    https://eli.thegreenplace.net/2016/basics-of-using-the-readline-library/
// Update README.md after adding new commands
string arr[] = {"testing", "initCamera", "expSettings", "intTime", "frameSettings", "reconfigASIC", "acquire",
                "readASIC_block", "readASIC", "writeASIC", "printRegs", "updateRegMap", "setParam", "getParam",
                "readASICconfig", "getInputs", "setInputs", "setGain", "getGain", "setNBuffer", "getNBuffer",
                "setCapComp", "getCapComp", "setFiltPole", "getFiltPole", "setNOut", "getNOut",
                "setClock", "getClock", "setPhase", "getPhase", "findPhase", "getErrors", "resetErrors",
                "setVerbose", "getVerbose", "exit", "quit", "getPower", "getVoltages", "setLED",
                "powerOff", "powerOn", "readMACIE", "writeMACIE", "haltAcq", "configBuffers", "runTuneAcq"};
vector<string> vocabulary(arr, arr + sizeof(arr) / sizeof(arr[0]));

char *completion_generator(const char *text, int state)
{
    // This function is called with state=0 the first time; subsequent calls are
    // with a nonzero state. state=0 can be used to perform one-time
    // initialization for this completion session.
    static std::vector<std::string> matches;
    static size_t match_index = 0;

    if (state == 0)
    {
        // During initialization, compute the actual matches for 'text' and keep
        // them in a static vector.
        matches.clear();
        match_index = 0;

        // Collect a vector of matches: vocabulary words that begin with text.
        std::string textstr = std::string(text);
        std::vector<std::string>::iterator it;
        for (it = vocabulary.begin(); it != vocabulary.end(); it++)
        {
            string word = *it;
            if ((word.size() >= textstr.size()) && (word.compare(0, textstr.size(), textstr) == 0))
            {
                matches.push_back(word);
            }
        }
    }

    if (match_index >= matches.size())
    {
        // We return nullptr to notify the caller no more matches are available.
        return NULL;
    }
    else
    {
        // Return a malloc'd char* for the match. The caller frees it.
        return strdup(matches[match_index++].c_str());
    }
}

char **completer(const char *text, int start, int end)
{
    // Don't do filename completion even if our generator finds no matches.
    rl_attempted_completion_over = 1;

    // Note: returning nullptr here will make readline use the default filename
    // completer.
    return rl_completion_matches(text, completion_generator);
}

int initialize(string configFile, MACIE_Settings *ptUserData)
{
    std::cout << std::fixed << std::setprecision(1);
    std::cout << "MACIE Library Version: " << MACIE_LibVersion() << std::endl;

    if (create_param_struct(ptUserData, LOG_INFO) == false)
    {
        std::cout << "create_param_struct failed. Exiting." << std::endl;
        return -1;
    }

    // ptUserData->offline_develop = true;

    // Initialize MACIE interface
    if (MACIE_Init() != MACIE_OK)
    {
        verbose_printf(LOG_ERROR, ptUserData, "MACIE_Init failed: %s\n", MACIE_Error());
        free_resources(ptUserData);
        return -1;
    }

    return 0;
}

void acquire(bool no_recon, MACIE_Settings *ptUserData )
{
    verbose_printf(LOG_INFO, ptUserData, "Starting Data Acquisition...\n");

    // First reconfigure ASIC in case we forgot
    // Then trigger image acquisition
    // Then download and save data
    bool bOutput = true;
    if (!no_recon)
    {
        timestamp_t t0 = get_timestamp();
        bOutput = ReconfigureASIC(ptUserData);
        timestamp_t t1 = get_timestamp();
        double time_taken = (t1 - t0) / 1000000.0L;
        verbose_printf(LOG_INFO, ptUserData, "ReconfigureASIC() took %f seconds to execute.\n", time_taken);
    }

    if (bOutput == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Reconfigure ASIC failed at %s()\n", __func__);
    }
    else if (AcquireDataGigE(ptUserData, false) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "AcquireDataGigE failed at %s()\n", __func__);
    }
    else
    {
        timestamp_t t0 = get_timestamp();
        DownloadAndSaveAllUSB(ptUserData);
        timestamp_t t1 = get_timestamp();
        double time_taken = (t1 - t0) / 1000000.0L;
        printf("\nDownloadAndSaveAllUSB() took %f seconds to execute.\n", time_taken);
    }

    // Check for errors
    GetErrorCounters(ptUserData, false);
    uint errCnts = 0;
    for (int j = 0; j < MACIE_ERROR_COUNTERS; j++)
        errCnts += (uint)ptUserData->errArr[j];
    if (errCnts > 0)
    {
        verbose_printf(LOG_WARNING, ptUserData, "MACIE Errors encountered!\n");
        if (get_verbose(ptUserData) <= LOG_WARNING)
            GetErrorCounters(ptUserData, true);

        // If just science errors, then reset error counters
        errCnts = 0;
        for (int j = 0; j < 25; j++)
            errCnts += (uint)ptUserData->errArr[j];
        if (errCnts == 0)
        {
            verbose_printf(LOG_INFO, ptUserData, "Resetting error counters...\n");
            ResetErrorCounters(ptUserData);
        }
    }
}

void toggle_offline_testing(bool offline_testing, MACIE_Settings *ptUserData)
{
    ptUserData->offline_develop = offline_testing;
}

// Run command line executable:
//  $ ./macieacq config_files/basic_slow_HxRG_warm.cfg
int main(int argc, char *argv[])
{
    string option, configFile;
    unsigned int val = 0;
    unsigned short addr = 0;
    struct MACIE_Settings *ptUserData = new MACIE_Settings;;

    // Get config file and copy to string
    if (argc == 1)
    {
        std::cout << "\nNo config file name passed..." << std::endl;
        return -1;
    }
    else if (argc > 2)
    {
        std::cout << "\nToo many argument passed. Requires only 1." << std::endl;
        return -1;
    }
    else
    {
        string configFile = argv[1];
         
        if(initialize(configFile, ptUserData) == -1)
        {
            return -1;
        }
    }

    // Command line info
    string line;
    int argc2 = 0;

    map<string, regInfo>::iterator it;
    regInfo *reg;

    rl_attempted_completion_function = completer;

    char *buf;
    std::cout << "\nEnter a command. Type 'exit' or 'quit' to end. \n";
    std::cout << "Use Tab key to print list of commands (tab completion enabled). \n";
    do
    {

        buf = readline(">> ");
        line = string(buf);

        if (strlen(buf) > 0)
        {
            add_history(buf);
        }

        argc2 = countWords(buf) + 1; // Number of words in input
        char *argv2[argc2];          // Create char pointer array

        // Separate words to array positions
        argv2[0] = argv[0];
        argv2[1] = strtok(buf, " =");
        verbose_printf(LOG_DEBUG, ptUserData, "0 %i %s\n", argc2, argv2[0]);
        verbose_printf(LOG_DEBUG, ptUserData, "1 %i %s\n", argc2, argv2[1]);
        for (int i = 2; i < argc2; ++i)
        {
            argv2[i] = strtok(NULL, " =");
            verbose_printf(LOG_DEBUG, ptUserData, "%i %i %s\n", i, argc2, argv2[i]);
        }

        // Parse input options
        InputParser input2(argc2, argv2);

        ////////////////////////////////////////////////////////////////////////////////
        // Enable/disable offline software testing/debugging
        if (input2.cmdOptionExists("testing"))
        {
            option = input2.getCmdOption("testing");
            transform(option.begin(), option.end(), option.begin(), ::tolower);
            if ((option == "true") || (option == "1"))
            {
                verbose_printf(LOG_INFO, ptUserData, "Offline testing enabled.\n");
                ptUserData->offline_develop = true;
            }
            else if ((option == "false") || (option == "0"))
            {
                verbose_printf(LOG_INFO, ptUserData, "Offline testing disabled.\n");
                ptUserData->offline_develop = false;
            }
            else
            {
                printf("Usage: testing true/false\n");
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Initialize Camera (MACIE+ASIC+Detector)
        if (input2.cmdOptionExists("initCamera"))
        {
            verbose_printf(LOG_INFO, ptUserData, "Initializing Camera...\n");
            if (InitCamera(configFile, MACIE_GigE, ptUserData) == false)
                verbose_printf(LOG_ERROR, ptUserData, "InitCamera failed at %s()\nReturning.\n", __func__);
            else
                verbose_printf(LOG_INFO, ptUserData, "InitCamera Completed\n");

            // unsigned int valOut;
            // unsigned int bitmask = (1 << 11) - 1;
            // float volts = 0;
            // unsigned int dac_val = 0;

            // reg = &(ptUserData->RegMap["VReset1"]);
            // ReadASICBits(ptUserData, reg, &valOut);
            // valOut &= bitmask;

            // volts = ConvertDACToV(valOut);
            // printf("h%04x[0:10] = 0x%04x (%f V)\n", reg->addr, valOut, volts);
            // dac_val = ConvertVToDAC(volts);
            // printf("%f V -> 0x%04x\n", volts, dac_val);

            // reg = &(ptUserData->RegMap["DSub1"]);
            // ReadASICBits(ptUserData, reg, &valOut);
            // valOut &= bitmask;

            // volts = ConvertDACToV(valOut);
            // printf("h%04x[0:10] = 0x%04x (%f V)\n", reg->addr, valOut, volts);
            // dac_val = ConvertVToDAC(volts);
            // printf("%f V -> 0x%04x\n", volts, dac_val);
        }

        ////////////////////////////////////////////////////////////////////////////////
        // MACIE Power and Voltage values
        if (input2.cmdOptionExists("getPower"))
        {
            bool pArr[MACIE_PWR_CTRL_SIZE];
            GetPower(ptUserData, pArr);
        }
        if (input2.cmdOptionExists("getVoltages"))
        {
            float vArr[MACIE_PWR_DAC_SIZE];
            GetVoltages(ptUserData, vArr);
        }
        if (input2.cmdOptionExists("powerOff"))
        {
            SetPowerASIC(ptUserData, false);
        }
        if (input2.cmdOptionExists("powerOn"))
        {
            bool bEn = false;
            GetPowerASIC(ptUserData, &bEn);
            if (bEn == true)
            {
                verbose_printf(LOG_INFO, ptUserData, "ASIC already powered ON\n");
            }
            else
            {
                if (SetPowerASIC(ptUserData, true) == true)
                {
                    LoadASIC(ptUserData);
                    ParseConfig(configFile, ptUserData, true);
                }
            }
        }
        if (input2.cmdOptionExists("setLED"))
        {
            option = input2.getCmdOption("setLED");
            if (!option.empty())
            {
                val = str2uint(option);
                SetLED(ptUserData, val);
            }
            else
            {
                printf("Usage: setLED [0-4]\n");
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Update Exposure Settings
        if (input2.cmdOptionExists("expSettings"))
        {

            // Grab current values
            bool bSave = ptUserData->bSaveData;
            unsigned int ncoadds = ptUserData->uiNumCoadds;
            unsigned int nsaved_ramps = ASIC_NRamps(ptUserData, false, 0) / ncoadds;
            unsigned int ngroups = ASIC_NGroups(ptUserData, false, 0);
            unsigned int nreads = ASIC_NReads(ptUserData, false, 0);
            unsigned int ndrops = ASIC_NDrops(ptUserData, false, 0);
            unsigned int nresets = ASIC_NResets(ptUserData, false, 0);

            // Print help
            option = input2.getCmdOption("expSettings");
            // if ( (input2.cmdOptionExists("--help")) || option.empty() )
            if (input2.cmdOptionExists("--help"))
            {
                printf("Usage: expSettings --save bool -c ncoadds -i nseq -g ngroups -r nreads -s ndrops -k nresets\n");
            }
            else
            {
                verbose_printf(LOG_INFO, ptUserData, "Updating Exposure Settings...\n");

                // Save Data?
                option = input2.getCmdOption("--save");
                if (!option.empty())
                {
                    transform(option.begin(), option.end(), option.begin(), ::tolower);
                    bSave = ((option == "false") || (option == "0")) ? false : true;
                }

                // Coadds
                option = input2.getCmdOption("-c");
                if (!option.empty())
                    ncoadds = atoi(option.c_str());
                // Ramps (Integrations)
                option = input2.getCmdOption("-i");
                if (!option.empty())
                    nsaved_ramps = atoi(option.c_str());
                // Groups
                option = input2.getCmdOption("-g");
                if (!option.empty())
                    ngroups = atoi(option.c_str());
                // Reads
                option = input2.getCmdOption("-r");
                if (!option.empty())
                    nreads = atoi(option.c_str());
                // Drops (Spin)
                option = input2.getCmdOption("-s");
                if (!option.empty())
                    ndrops = atoi(option.c_str());
                // Resets
                option = input2.getCmdOption("-k");
                if (!option.empty())
                    nresets = atoi(option.c_str());

                set_exposure_settings(ptUserData, bSave, ncoadds, nsaved_ramps,
                                      ngroups, nreads, ndrops, nresets);
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Update Frame Settings
        if (input2.cmdOptionExists("intTime"))
        {

            // Grab current values
            bool bSave = ptUserData->bSaveData;
            unsigned int ncoadds = ptUserData->uiNumCoadds;
            unsigned int nsaved_ramps = ASIC_NRamps(ptUserData, false, 0) / ncoadds;
            unsigned int ngroups = ASIC_NGroups(ptUserData, false, 0);
            unsigned int nreads = ASIC_NReads(ptUserData, false, 0);
            unsigned int ndrops = ASIC_NDrops(ptUserData, false, 0);
            unsigned int nresets = ASIC_NResets(ptUserData, false, 0);

            double tint_ms = 0;
            unsigned int ngmax = 0;

            // Print help
            option = input2.getCmdOption("intTime");
            if ((input2.cmdOptionExists("--help")) || option.empty())
            {
                printf("Usage: intTime -t tint_ms -g ngmax\n");
            }
            else
            {

                option = input2.getCmdOption("-t");
                if (!option.empty())
                    tint_ms = strtod(option.c_str(), NULL);
                // Ramps (Integrations)
                option = input2.getCmdOption("-g");
                if (!option.empty())
                    ngmax = atoi(option.c_str());

                calc_ramp_settings(ptUserData, tint_ms, ngmax, &ngroups, &ndrops, &nreads);
                set_exposure_settings(ptUserData, bSave, ncoadds, nsaved_ramps,
                                      ngroups, nreads, ndrops, nresets);
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Update Frame Settings
        if (input2.cmdOptionExists("frameSettings"))
        {

            // Grab current values
            unsigned int x1 = ASIC_getX1(ptUserData);
            unsigned int x2 = ASIC_getX2(ptUserData);
            unsigned int y1 = ASIC_getY1(ptUserData);
            unsigned int y2 = ASIC_getY2(ptUserData);
            bool bHorzWin = (bool)ASIC_WinHorz(ptUserData, false, 0);
            bool bVertWin = (bool)ASIC_WinVert(ptUserData, false, 0);

            // Print help
            option = input2.getCmdOption("frameSettings");
            if ((input2.cmdOptionExists("--help")) || option.empty())
            {
                printf("Usage: frameSettings --xWin bool --yWin bool -x1 uint -x2 uint -y1 uint -y2 uint\n");
            }
            else
            {
                verbose_printf(LOG_INFO, ptUserData, "Updating Frame Settings...\n");

                // Horizontal Window
                option = input2.getCmdOption("--xWin");
                if (!option.empty())
                {
                    transform(option.begin(), option.end(), option.begin(), ::tolower);
                    bHorzWin = ((option == "false") || (option == "0")) ? false : true;
                }
                // Vertical Window
                option = input2.getCmdOption("--yWin");
                if (!option.empty())
                {
                    transform(option.begin(), option.end(), option.begin(), ::tolower);
                    bVertWin = ((option == "false") || (option == "0")) ? false : true;
                }

                // update x1
                option = input2.getCmdOption("-x1");
                if (!option.empty())
                    x1 = atoi(option.c_str());
                // update x2
                option = input2.getCmdOption("-x2");
                if (!option.empty())
                    x2 = atoi(option.c_str());
                // update y1
                option = input2.getCmdOption("-y1");
                if (!option.empty())
                    y1 = atoi(option.c_str());
                // update y2
                option = input2.getCmdOption("-y2");
                if (!option.empty())
                    y2 = atoi(option.c_str());

                set_frame_settings(ptUserData, bHorzWin, bVertWin, x1, x2, y1, y2);
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Update PreAmp Inputs, Gain, Cap Comp, and Filter Pole
        if (input2.cmdOptionExists("setInputs"))
        {
            option = input2.getCmdOption("setInputs");
            if (!option.empty())
            {
                // Always assume input value is 16bit HEX string
                val = strtoul(option.c_str(), NULL, 16);
                val = ASIC_Inputs(ptUserData, true, val);
            }
            else
            {
                printf("Usage: setInputs 0xaaaa\n");
            }
        }
        if (input2.cmdOptionExists("setGain"))
        {
            option = input2.getCmdOption("setGain");
            if (!option.empty())
            {
                val = str2uint(option);
                val = ASIC_Gain(ptUserData, true, val);
            }
            else
            {
                printf("Usage: setGain [0-15]\n");
            }
        }
        if (input2.cmdOptionExists("setCapComp"))
        {
            option = input2.getCmdOption("setCapComp");
            if (!option.empty())
            {
                val = str2uint(option);
                val = ASIC_CapComp(ptUserData, true, val);
            }
            else
            {
                printf("Usage: setCapComp [0-63]\n");
            }
        }
        if (input2.cmdOptionExists("setFiltPole"))
        {
            option = input2.getCmdOption("setFiltPole");
            if (!option.empty())
            {
                val = str2uint(option);
                val = ASIC_FiltPole(ptUserData, true, val);
            }
            else
            {
                printf("Usage: setFiltPole [0-15]\n");
            }
        }
        if (input2.cmdOptionExists("setNOut"))
        {
            option = input2.getCmdOption("setNOut");
            if (!option.empty())
            {
                val = str2uint(option);
                val = ASIC_NumOutputs(ptUserData, true, val);
            }
            else
            {
                printf("Usage: setNOut [1,2,4,16,32]\n");
            }
        }
        if (input2.cmdOptionExists("getInputs"))
            ASIC_Inputs(ptUserData, false, 0);
        if (input2.cmdOptionExists("getGain"))
            ASIC_Gain(ptUserData, false, 0);
        if (input2.cmdOptionExists("getCapComp"))
            ASIC_CapComp(ptUserData, false, 0);
        if (input2.cmdOptionExists("getFiltPole"))
            ASIC_FiltPole(ptUserData, false, 0);
        if (input2.cmdOptionExists("getNOut"))
            ASIC_NumOutputs(ptUserData, false, 0);

        ////////////////////////////////////////////////////////////////////////////////
        // Acquire data
        if (input2.cmdOptionExists("acquire"))
        {
            acquire(input2.cmdOptionExists("--no_recon"), ptUserData);
        }
        // Halt a failed acquisition
        if (input2.cmdOptionExists("haltAcq"))
        {
            // What is the proper order?
            HaltCameraAcq(ptUserData);
            delay(300);
            CloseUSBScienceInterface(ptUserData);
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Read specific MACIE register
        if (input2.cmdOptionExists("readMACIE"))
        {
            option = input2.getCmdOption("--addr");
            if (!option.empty())
            {
                addr = strtoul(option.c_str(), NULL, 16);
                MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, addr, &val);
                printf("h%04x = 0x%04x\n", addr, val);
            }
            else
            {
                // In case we forget the --addr argument
                // (which happens all the time)
                option = input2.getCmdOption("readMACIE");
                if (!option.empty())
                {
                    addr = strtoul(option.c_str(), NULL, 16);
                    MACIE_ReadMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, addr, &val);
                    printf("h%04x = 0x%04x\n", addr, val);
                }
                else
                {
                    printf("Usage: readMACIE --addr 0x4000\n");
                }
            }
        }
        ////////////////////////////////////////////////////////////////////////////////
        // Write MACIE register
        // Address and values assumed to be in HEX
        if (input2.cmdOptionExists("writeMACIE"))
        {
            // Get address
            option = input2.getCmdOption("--addr");
            if (option.empty())
            {
                addr = 0;
            }
            else
            {
                addr = strtoul(option.c_str(), NULL, 16);
            }

            // Get value
            option = input2.getCmdOption("--val");
            if (option.empty())
            {
                val = 0;
            }
            else
            {
                val = str2uint(option); // Checks if hex (0x) or dec
                // val = strtoul(option.c_str(), NULL, 16);
            }

            if (addr != 0)
            {
                MACIE_WriteMACIEReg(ptUserData->handle, ptUserData->slctMACIEs, addr, val);
            }
            else
            {
                printf("Usage: writeMACIE --addr 0x4000 --val 0x1\n");
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Read specific ASIC register
        if (input2.cmdOptionExists("readASIC"))
        {
            option = input2.getCmdOption("--addr");
            if (!option.empty())
            {
                addr = strtoul(option.c_str(), NULL, 16);
                ReadASICReg(ptUserData, addr, &val);
                printf("h%04x = 0x%04x\n", addr, val);
            }
            else
            {
                // In case we forget the --addr argument
                // (which happens all the time)
                option = input2.getCmdOption("readASIC");
                if (!option.empty())
                {
                    addr = strtoul(option.c_str(), NULL, 16);
                    ReadASICReg(ptUserData, addr, &val);
                    printf("h%04x = 0x%04x\n", addr, val);
                }
                else
                {
                    printf("Usage: readASIC --addr 0x4000\n");
                }
            }
        }
        ////////////////////////////////////////////////////////////////////////////////
        // Write ASIC register
        // Address and values assumed to be in HEX
        if (input2.cmdOptionExists("writeASIC"))
        {
            // Get address
            option = input2.getCmdOption("--addr");
            if (option.empty())
            {
                addr = 0;
            }
            else
            {
                addr = strtoul(option.c_str(), NULL, 16);
            }

            // Get value
            option = input2.getCmdOption("--val");
            if (option.empty())
            {
                val = 0;
            }
            else
            {
                val = str2uint(option); // Checks if hex (0x) or dec
                // val = strtoul(option.c_str(), NULL, 16);
            }

            if (addr != 0)
            {
                WriteASICReg(ptUserData, addr, val);
            }
            else
            {
                printf("Usage: writeASIC --addr 0x4000 --val 0x1\n");
            }
        }
        ////////////////////////////////////////////////////////////////////////////////
        // Read specific ASIC register block
        if (input2.cmdOptionExists("readASIC_block"))
        {
            // Get address
            option = input2.getCmdOption("--addr");
            if (option.empty())
            {
                addr = 0;
            }
            else
            {
                addr = strtoul(option.c_str(), NULL, 16);
            }

            // Get number of registers
            int nreg = 0;
            option = input2.getCmdOption("--nreg");
            if (!option.empty())
            {
                nreg = str2uint(option); // Checks if hex (0x) or dec
            }

            if ((addr != 0) && (nreg != 0))
            {
                unsigned int val_arr[nreg] = {};
                ReadASICBlock(ptUserData, addr, nreg, &val_arr[0]);
                for (int i = 0; i < nreg; i++)
                    printf("  h%04x = 0x%04x\n", addr + i, val_arr[i]);
            }
            else
            {
                printf("Usage: readASIC_block --addr 0x6000 --nreg 16\n");
            }
        }
        ////////////////////////////////////////////////////////////////////////////////
        // Read specific ASIC register block
        if (input2.cmdOptionExists("readASICconfig"))
        {
            // Get address
            option = input2.getCmdOption("--addr");
            if (option.empty())
            {
                addr = 0;
            }
            else
            {
                addr = strtoul(option.c_str(), NULL, 16);
            }

            // Get number of registers
            int nreg = 0;
            option = input2.getCmdOption("--nreg");
            if (!option.empty())
            {
                nreg = str2uint(option); // Checks if hex (0x) or dec
            }

            if ((addr != 0) && (nreg != 0))
            {
                readASICconfig(ptUserData, addr, nreg);
            }
            else
            {
                printf("Usage: readASICconfig --addr 0x6000 --nreg 16\n");
            }
        }
        ////////////////////////////////////////////////////////////////////////////////
        // Update the ASIC reg settings stored in ptUserData
        if (input2.cmdOptionExists("updateRegMap"))
        {
            if (GetASICSettings(ptUserData) == false)
            {
                verbose_printf(LOG_ERROR, ptUserData, "  GetASICSettings failed to complete.\n");
                return false;
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Print all stored ASIC registry information in RegMap
        if (input2.cmdOptionExists("printRegs"))
        {
            verbose_printf(LOG_INFO, ptUserData, "Current Registry Configuration\n");
            for (it = ptUserData->RegMap.begin(); it != ptUserData->RegMap.end(); it++)
            {
                reg = &it->second;
                printf("%s : h%04x <%i:%i> = 0x%04x\n",
                       it->first.c_str(), reg->addr, reg->bit1, reg->bit0, reg->value);
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Set/Get number of buffers
        if (input2.cmdOptionExists("setNBuffer"))
        {
            option = input2.getCmdOption("setNBuffer");
            if (!option.empty())
            {
                val = str2uint(option);
                SetNBuffer(ptUserData, (short)val);
                verbose_printf(LOG_INFO, ptUserData, "  nBuffer = %i\n", ptUserData->nBuffer);
            }
            else
            {
                printf("Usage: setNBuffer [1-100]\n");
            }
        }
        if (input2.cmdOptionExists("getNBuffer"))
        {
            verbose_printf(LOG_INFO, ptUserData, "  nBuffer = %i\n", ptUserData->nBuffer);
        }
        if (input2.cmdOptionExists("configBuffers"))
        {
            // Print help
            option = input2.getCmdOption("configBuffers");
            if (input2.cmdOptionExists("--help"))
            {
                printf("Usage: configBuffers --sciFunc bool --buffsize int --nbuf int\n");
            }
            else if ((input2.cmdOptionExists("--buffsize")) || (input2.cmdOptionExists("--nbuf")))
            {
                // Defaults
                int buffsize = 1024 * 1024;
                short nbuf = 1;

                option = input2.getCmdOption("--buffsize");
                if (!option.empty())
                    buffsize = (int)str2uint(option);

                option = input2.getCmdOption("--nbuf");
                if (!option.empty())
                    nbuf = (short)str2uint(option);

                test_buff_config(ptUserData, buffsize, nbuf);
            }
            else // if ( input2.cmdOptionExists("--sciFunc") )
            {
                // Use MACIE_ReadUSBScienceData() instead of MACIE_ReadUSBScienceFrame()?
                option = input2.getCmdOption("--sciFunc");
                if (!option.empty())
                {
                    transform(option.begin(), option.end(), option.begin(), ::tolower);
                    ptUserData->bUseSciDataFunc = ((option == "false") || (option == "0")) ? false : true;
                }

                ConfigBuffers(ptUserData);
                if (VerifyBuffers(ptUserData) == false)
                    verbose_printf(LOG_ERROR, ptUserData, "VerifyBuffers failed!\n");
                else
                    verbose_printf(LOG_INFO, ptUserData, "VerifyBuffers succeeded.\n");
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Reconfigure ASIC after updating user parameters
        if (input2.cmdOptionExists("reconfigASIC"))
        {
            verbose_printf(LOG_INFO, ptUserData, "Reconfiguring ASIC Registers...\n");
            if (ReconfigureASIC(ptUserData) == false)
                verbose_printf(LOG_ERROR, ptUserData, "Reconfigure failed at %s()\n", __func__);
            else
                verbose_printf(LOG_INFO, ptUserData, "Done.\n");
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Run tuning acquisitions
        if (input2.cmdOptionExists("runTuneAcq"))
        {
            option = input2.getCmdOption("runTuneAcq");
            if ((input2.cmdOptionExists("--help")) || (option.empty()))
            {
                printf("Usage: runTuneAcq filename.txt\n");
            }
            else
            {
                timestamp_t t0 = get_timestamp();
                run_asic_tune_file(option, ptUserData);
                timestamp_t t1 = get_timestamp();

                double time_taken = (t1 - t0) / 1000000.0L;
                printf("\nrun_asic_tune_file() took %f seconds to execute.\n", time_taken);
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Set/Get MACIE Phase Shift parameters
        // Bit 8: enable ASIC phase shift, otherwise phase shift bits 7-0 are ignored
        // Bit 7-0: valid values range from 0x00 to 0xFF
        if (input2.cmdOptionExists("setPhase"))
        {
            option = input2.getCmdOption("setPhase");
            if (!option.empty())
            {
                // val = str2uint(option);
                val = strtoul(option.c_str(), NULL, 16);
                SetMACIEPhaseShift(ptUserData, (unsigned short)val);
            }
            else
            {
                printf("Usage: setPhase 0x01e0\n");
            }
        }
        if (input2.cmdOptionExists("getPhase"))
            GetMACIEPhaseShift(ptUserData);
        if (input2.cmdOptionExists("findPhase"))
        {
            ushort val1 = 0;
            ushort val2 = 0;

            // Get val1
            option = input2.getCmdOption("--val1");
            if (!option.empty())
                val1 = strtoul(option.c_str(), NULL, 16);
            // Get val2
            option = input2.getCmdOption("--val2");
            if (!option.empty())
                val2 = strtoul(option.c_str(), NULL, 16);

            if ((val1 == 0) || (val2 == 0))
            {
                printf("Usage: findPhase --val1 0x01b0 --val2 0x01e0\n");
            }
            else
            {
                FindOptimalPhaseShift(ptUserData, val1, val2);
            }
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Set/Get MACIE Clock Rate
        if (input2.cmdOptionExists("setClock"))
        {
            option = input2.getCmdOption("setClock");
            if (!option.empty())
            {
                val = str2uint(option);
                // val = strtoul(option.c_str(), NULL, 16);
                SetMACIEClockRate(ptUserData, val);
                verbose_printf(LOG_INFO, ptUserData, "  MACIE Clock Rate = %i MHz\n", ptUserData->clkRateM);
            }
            else
            {
                printf("Usage: setClock [5-80]\n");
            }
        }
        if (input2.cmdOptionExists("getClock"))
        {
            GetMACIEClockRate(ptUserData);
            verbose_printf(LOG_INFO, ptUserData, "  MACIE Clock Rate = %i MHz\n", ptUserData->clkRateM);
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Reset/Read MACIE error counters
        if (input2.cmdOptionExists("resetErrors"))
            ResetErrorCounters(ptUserData);
        if (input2.cmdOptionExists("getErrors"))
            GetErrorCounters(ptUserData, true);

        ////////////////////////////////////////////////////////////////////////////////
        // Set/Get Log Level Settings
        option = input2.getCmdOption("setVerbose");
        transform(option.begin(), option.end(), option.begin(), ::toupper);
        if (!option.empty())
        {
            set_verbose(ptUserData, convert_log_type(option.c_str()));
            printf("New log levels: %s\n", convert_log_type_str(get_verbose(ptUserData)));
        }
        if (input2.cmdOptionExists("getVerbose"))
        {
            printf("Log level settings: %s\n", convert_log_type_str(get_verbose(ptUserData)));
        }

        ////////////////////////////////////////////////////////////////////////////////
        // Update ASIC setting
        if (input2.cmdOptionExists("setParam"))
        {
            // Get parameter name
            string pname = input2.getCmdOption("--param");
            if (pname.empty())
                pname = input2.getCmdOption("-p");

            // Get value
            option = input2.getCmdOption("--val");
            if (option.empty())
                option = input2.getCmdOption("-v");

            if (pname.empty() || option.empty())
            {
                printf("Usage: setParam --param Name --val 15 (or 0xf)\n");
            }
            else
            {
                val = str2uint(option);
                SetASICParameter(ptUserData, pname, val);
            }
        }
        if (input2.cmdOptionExists("getParam"))
        {
            option = input2.getCmdOption("--param");
            if (option.empty())
                option = input2.getCmdOption("-p");
            // If we forgot the --param or -p tag, assume the next string is the param
            if (option.empty())
                option = input2.getCmdOption("getParam");

            if (!option.empty())
            {
                if (GetASICParameter(ptUserData, option, &val) == true)
                    printf("%s = %i (0x%04x)\n", option.c_str(), val, val);
            }
            else
            {
                // In case we forget the --param argument
                // (which happens regularly)
                // option = input2.getCmdOption("getP"); // Is this a typo?? (JML 7/16/2019)
                option = input2.getCmdOption("getParam");
                if ((option.empty() == true) || (option.compare("--param") == 0))
                {
                    printf("Usage: getParam --param Name\n");
                }
                else
                {
                    if (GetASICParameter(ptUserData, option, &val) == true)
                        printf("%s = %i (0x%04x)\n", option.c_str(), val, val);
                }
            }
        }

        // readline malloc's a new buffer every time.
        free(buf);

    } while ((line != "exit") && (line != "quit"));

    SetPowerASIC(ptUserData, false);

    // Call MACIE_Free
    if (free_resources(ptUserData) == false)
        return -1;
    else
        return 0;
}

////////////////////////////////////////////////////////////////////////////////
/// \brief InitCamera Initialize camera performing the following steps:
///   1. Select appropriate MACIE and ASIC registry Files.
///   2. Setup ASIC registry address map for local storage in ptUserData.
///   3. Check connection interfaces
///   4. Get handle for (currently USB connection only)
///   5. Get available MACIEs associated with handle
///   6. Initialize MACIE and ASIC
/// for the hardware.
bool InitCamera(string configFile, MACIE_Connection connection, MACIE_Settings *ptUserData)
{
    // Store info in user settings
    ptUserData->connection = connection;

    ////////////////////////////////////////////////////////////////////////////////
    // 1. Save directory setup
    // Set load files and detector info from config files
    if (ParseConfig(configFile, ptUserData, false) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "ParseConfig failed at %s()\n", __func__);
        return false;
    }
    printf("detType = %s\n", convert_camera_type_str(ptUserData->DetectorType));
    printf("detMode = %s\n", convert_camera_mode_str(ptUserData->DetectorMode));

    ////////////////////////////////////////////////////////////////////////////////
    // 1. Save directory setup

    // Time/date info
    time_t t1 = time(0);          // get time now
    struct tm *now = gmtime(&t1); // in GMT

    // Save directory
    // If save directory is not set (equals "") then set to default ~/data/$DATE/
    char buffer[80];
    std::stringstream ss;
    string homedir = getenv("HOME");
    if (ptUserData->saveDir.compare("") == 0)
    {
        strftime(buffer, 80, "/data/%Y%m%d/", now);
        ss << buffer;
        ptUserData->saveDir = homedir + ss.str();
    }
    else
    {
        strftime(buffer, 80, "%Y%m%d/", now);
        ss << buffer;
        ptUserData->saveDir = ptUserData->saveDir + ss.str();
    }

    // Add date to filename prefix
    char buffer2[80];
    std::stringstream ss2;
    strftime(buffer2, 80, "%Y%m%d_", now);
    ss2 << buffer2;
    ptUserData->filePrefix = ptUserData->filePrefix + ss2.str();

    printf("saveDir: %s\n", ptUserData->saveDir.c_str());
    printf("prefix: %s\n", ptUserData->filePrefix.c_str());

    // Create save directory
    struct stat st = {0};
    if (stat(ptUserData->saveDir.c_str(), &st) == -1)
    {
        verbose_printf(LOG_INFO, ptUserData, "Creating directory: %s\n", ptUserData->saveDir.c_str());
        mkdir(ptUserData->saveDir.c_str(), 0700);
    }

    ////////////////////////////////////////////////////////////////////////////////
    // 2. Set up registry address map
    //    Only defines addresses. No values yet.
    if (initRegMap(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "initRegMap failed at %s()\n", __func__);
        return false;
    }

    ////////////////////////////////////////////////////////////////////////////////
    // 3. Check interfaces
    verbose_printf(LOG_NONE, ptUserData, "\n"); // Print blank line
    if (CheckInterfaces(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "CheckInterfaces failed at %s()\n", __func__);
        return false;
    }
    verbose_printf(LOG_NONE, ptUserData, "\n"); // Print blank line

    ////////////////////////////////////////////////////////////////////////////////
    // 4. Get Handle for (GigE   only)
    if (GetHandleGigE(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "GetHandleGigE failed at %s()\n", __func__);
        return false;
    }

    ////////////////////////////////////////////////////////////////////////////////
    // 5. Get available MACIEs associated with handle
    if (GetAvailableMACIEs(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "GetAvailableMACIEs failed at %s()\n", __func__);
        return false;
    }

    ////////////////////////////////////////////////////////////////////////////////
    // 6. Initialize MACIE and ASIC
    verbose_printf(LOG_NONE, ptUserData, "\n"); // Print blank line
    if (InitializeASIC(ptUserData) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "InitializeASIC failed at %s()\n", __func__);
        return false;
    }

    ////////////////////////////////////////////////////////////////////////////////
    // 7. Update ASIC register settings from config file
    if (ParseConfig(configFile, ptUserData, true) == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "ParseConfig failed at %s()\n", __func__);
        return false;
    }

    verbose_printf(LOG_DEBUG, ptUserData, " %s returns true\n", __func__);
    return true;
}

// Run this command before closing main program.
bool free_resources(MACIE_Settings *ptUserData)
{
    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    if (MACIE_Free() != MACIE_OK)
    {
        verbose_printf(LOG_ERROR, ptUserData, "MACIE_Free failed:\n %s\n", MACIE_Error());
        return false;
    }

    delete ptUserData;
    return true;
}

// returns number of words in char string
unsigned int countWords(char *str)
{
    int state = 0;
    unsigned wc = 0; // word count

    // Scan all characters one by one
    while (*str)
    {
        // If next character is a separator, set the state as 0
        // otherwise if already 0, set to 1 and increment wc
        if (*str == ' ' || *str == '\n' || *str == '\t')
            state = 0;
        else if (state == 0)
        {
            state = 1;
            ++wc;
        }
        // Move to next character
        ++str;
    }
    return wc;
}

// Test if string is HEX or decimal by presence of "0x"
unsigned int str2uint(string option)
{
    unsigned int val;
    if (option.find("0x") != string::npos)
        val = strtoul(option.c_str(), NULL, 16);
    else // Value is decimal
        val = atoi(option.c_str());

    return val;
}

bool ParseConfig(string configFile, MACIE_Settings *ptUserData, bool update_regs)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    string linebuffer;
    unsigned int linecount = 0;
    const string ws(" \t\n\r");
    const string delimiters("#;");

    string MACIEFile, ASICFile, ASICRegs;
    string str1, str2;

    // Open file to ifstream
    std::ifstream infile;
    infile.open(configFile.c_str());

    if (infile.is_open() == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Could not open file %s\n", configFile.c_str());
        return false;
    }
    else
    {
        while (std::getline(infile, linebuffer))
        {
            size_t first_nonws = linebuffer.find_first_not_of(ws);

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

            // Stream to str1 and str2
            std::istringstream iss(linebuffer);
            iss >> str1 >> str2;

            // Parse out firmware files, detector type/mode, and clkphase/rate
            if (update_regs == false)
            {
                // verbose_printf(LOG_INFO, ptUserData, "  str1: %s, str2: %s\n", str1.c_str(), str2.c_str());

                if (str1.compare("MACIEFile") == 0)
                    strncpy(ptUserData->MACIEFile, str2.c_str(), str2.size());
                if (str1.compare("MACIEslot") == 0)
                    ptUserData->bMACIEslot1 = (str2uint(str2) == 1) ? true : false;
                else if (str1.compare("ASICFile") == 0)
                    strncpy(ptUserData->ASICFile, str2.c_str(), str2.size());
                else if (str1.compare("ASICRegs") == 0)
                    strncpy(ptUserData->ASICRegs, str2.c_str(), str2.size());

                else if (str1.compare("saveDir") == 0)
                {
                    // Expand home directory?
                    if (str2.compare(0, 1, "~") == 0)
                        ptUserData->saveDir = getenv("HOME") + str2.substr(1);
                    else
                        ptUserData->saveDir = str2;

                    // Check that last element in string is a "/"
                    char LastChar = *(ptUserData->saveDir).rbegin();
                    std::stringstream ss;
                    ss << LastChar;
                    string LastStr = ss.str();
                    if (LastStr.compare("/") != 0)
                        ptUserData->saveDir = ptUserData->saveDir + string("/");

                    // Create save directory
                    struct stat st = {0};
                    if (stat(ptUserData->saveDir.c_str(), &st) == -1)
                    {
                        verbose_printf(LOG_INFO, ptUserData, "Creating directory: %s\n", ptUserData->saveDir.c_str());
                        mkdir(ptUserData->saveDir.c_str(), 0700);
                    }
                }
                else if (str1.compare("filePrefix") == 0)
                {
                    // std::string::iterator it = str2.rbegin();
                    char LastChar = *str2.rbegin();

                    std::stringstream ss;
                    ss << LastChar;
                    string LastStr = ss.str();
                    if (LastStr.compare("_") == 0)
                        ptUserData->filePrefix = str2;
                    else
                        ptUserData->filePrefix = str2 + string("_");
                }

                else if (str1.compare("DetType") == 0)
                {
                    ptUserData->DetectorType = convert_camera_type(str2.c_str());
                }
                else if (str1.compare("DetMode") == 0)
                {
                    ptUserData->DetectorMode = convert_camera_mode(str2.c_str());
                    if (ptUserData->DetectorMode == CAMERA_MODE_FAST)
                    {
                        ptUserData->clkRateMDefault = 80;
                        ptUserData->clkPhaseDefault = 0x1e0;
                    }
                    else if (ptUserData->DetectorMode == CAMERA_MODE_SLOW)
                    {
                        ptUserData->clkRateMDefault = 10;
                        ptUserData->clkPhaseDefault = 0;
                    }
                }
            }
            else
            {
                // verbose_printf(LOG_INFO, ptUserData, "  str1: %s, str2: %s\n", str1.c_str(), str2.c_str());

                // Check for reg_ prefix
                if (str1.compare(0, 4, "reg_") == 0)
                {
                    string reg_name = str1.substr(4);
                    unsigned int reg_val = str2uint(str2);
                    SetASICParameter(ptUserData, reg_name, reg_val);
                }
                // Check for 0x addresses
                else if (str1.compare(0, 2, "0x") == 0)
                {
                    unsigned int reg_addr = strtoul(str1.c_str(), 0, 16);
                    unsigned int reg_val = str2uint(str2); // Can be HEX (0x) or DEC
                    WriteASICReg(ptUserData, reg_addr, reg_val);
                }
                else if (str1.compare("NumOutputs") == 0)
                    ASIC_NumOutputs(ptUserData, true, str2uint(str2));
                else if (str1.compare("Inputs") == 0)
                    ASIC_Inputs(ptUserData, true, str2uint(str2));
                else if (str1.compare("Gain") == 0)
                    ASIC_Gain(ptUserData, true, str2uint(str2));
                else if (str1.compare("CapComp") == 0)
                    ASIC_CapComp(ptUserData, true, str2uint(str2));
                else if (str1.compare("FiltPole") == 0)
                    ASIC_FiltPole(ptUserData, true, str2uint(str2));
                else if (str1.compare("clkPhase") == 0)
                    SetMACIEPhaseShift(ptUserData, str2uint(str2));
                else if (str1.compare("clkRateM") == 0)
                    SetMACIEClockRate(ptUserData, str2uint(str2));
            }

            ++linecount;
        }
        infile.close();
    }

    if (update_regs == true)
    {
        if (ReconfigureASIC(ptUserData) == false)
        {
            verbose_printf(LOG_ERROR, ptUserData, "Reconfigure failed at %s()\n", __func__);
            return false;
        }
    }

    return true;
}

bool test_buff_config(MACIE_Settings *ptUserData, int buffsize, short nbuf)
{

    unsigned int handle = ptUserData->handle;
    unsigned char slctMACIEs = ptUserData->slctMACIEs;
    unsigned short data_mode = (ptUserData->DetectorMode == CAMERA_MODE_SLOW) ? 0 : 3;

    verbose_printf(LOG_INFO, ptUserData, "test_buff_config(): Configuring science interface...\n");
    verbose_printf(LOG_INFO, ptUserData, "  nbuf = %i\n", nbuf);
    verbose_printf(LOG_INFO, ptUserData, "  buffsize = %i pixels\n", buffsize);

    unsigned long pixBuffer = (unsigned long)nbuf * (unsigned long)buffsize;
    unsigned long memAvail1 = GetMemAvailable(ptUserData);
    verbose_printf(LOG_INFO, ptUserData, "  MemAvail Start = %li MBytes\n", memAvail1 / 1024);

    if (ptUserData->offline_develop == false)
    {
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
            verbose_printf(LOG_ERROR, ptUserData, "Caught exception at %s.\n", __func__);
            std::cerr << e.what() << '\n';
            CloseUSBScienceInterface(ptUserData);

            return false;
        }
        delay(500);
    }

    unsigned long memAvail2 = GetMemAvailable(ptUserData);
    verbose_printf(LOG_INFO, ptUserData, "  MemAvail Diff = %li MBytes; Expected Buff = %li MBytes\n",
                   (memAvail1 - memAvail2) / 1024, 2 * pixBuffer / (1024 * 1024));

    // Testing frame download with no data
    ///////////////////
    // const int framesize = 1024*1024;
    // unsigned short *pData;
    // pData = new unsigned short [framesize]();

    // // DownloadRampUSB_Data(ptUserData, pData, framesize, 1, triggerTimeout, wait_delta)
    // if (DownloadDataUSB(ptUserData, &pData[0], (long)framesize, 1500)==false)
    // {
    //   verbose_printf(LOG_ERROR, ptUserData, "DownloadDataUSB failed at %s\n", __func__);
    // }
    // string filename = "/home/observer/test_data/blank.fits";
    // vector <long> naxis; naxis.push_back(1024); naxis.push_back(1024);
    // verbose_printf(LOG_INFO, ptUserData, "Writing: %s\n", filename.c_str());
    // if (WriteFITSRamp(pData, naxis, USHORT_IMG, filename) == false)
    // {
    //   verbose_printf(LOG_ERROR, ptUserData, "Failed to write FITS (16-bit) at %s\n", __func__);
    // }

    // delete[] pData;
    // End Testing
    ///////////////////////

    if (ptUserData->offline_develop == false)
    {
        CloseUSBScienceInterface(ptUserData);
        delay(500);
    }
    memAvail1 = GetMemAvailable(ptUserData);
    verbose_printf(LOG_INFO, ptUserData, "  MemAvail End = %li MBytes\n", memAvail1 / 1024);

    // verbose_printf(LOG_INFO, ptUserData, "No Seg Fault!\n");
    return true;
}

bool run_asic_tune_file(string tuneFile, MACIE_Settings *ptUserData)
{

    if (SettingsCheckNULL(ptUserData) == false)
        return false;

    string linebuffer;
    unsigned int linecount = 0;
    const string ws(" \t\n\r");
    const string delimiters("#;");

    string str1, str2;

    // Open file to ifstream
    std::ifstream infile;
    infile.open(tuneFile.c_str());

    if (infile.is_open() == false)
    {
        verbose_printf(LOG_ERROR, ptUserData, "Could not open file: %s\n", tuneFile.c_str());
        return false;
    }
    else
    {

        while (std::getline(infile, linebuffer))
        {
            size_t first_nonws = linebuffer.find_first_not_of(ws);

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

            // Stream to str1 and str2
            std::istringstream iss(linebuffer);
            iss >> str1 >> str2;

            // Check for reg_ prefix
            if (str1.compare(0, 4, "reg_") == 0)
            {
                string reg_name = str1.substr(4);
                unsigned int reg_val = str2uint(str2); // Can be HEX (0x) or DEC
                SetASICParameter(ptUserData, reg_name, reg_val);
            }
            // Check for 0x addresses
            else if (str1.compare(0, 2, "0x") == 0)
            {
                unsigned int reg_addr = strtoul(str1.c_str(), 0, 16);
                unsigned int reg_val = str2uint(str2); // Can be HEX (0x) or DEC
                WriteASICReg(ptUserData, reg_addr, reg_val);
                printf("  h%04x = 0x%04x\n", reg_addr, reg_val);
            }

            // Wait 1 sec for settling then take data
            delay(1000);

            // Acquire data
            if (AcquireDataUSB(ptUserData, false) == false)
            {
                verbose_printf(LOG_ERROR, ptUserData, "AcquireDataUSB failed at %s()\n", __func__);
            }
            else
            {
                DownloadAndSaveAllUSB(ptUserData);
            }

            // Check for errors
            GetErrorCounters(ptUserData, false);
            uint errCnts = 0;
            for (int j = 0; j < MACIE_ERROR_COUNTERS; j++)
                errCnts += (uint)ptUserData->errArr[j];
            if (errCnts > 0)
            {
                // verbose_printf(LOG_WARNING, ptUserData, "MACIE Errors encountered!\n");
                if (get_verbose(ptUserData) <= LOG_WARNING)
                    GetErrorCounters(ptUserData, false);

                // If just science errors, then reset error counters
                errCnts = 0;
                for (int j = 0; j < 25; j++)
                    errCnts += (uint)ptUserData->errArr[j];
                if (errCnts == 0)
                {
                    // verbose_printf(LOG_INFO, ptUserData, "Resetting error counters...\n");
                    ResetErrorCounters(ptUserData);
                }
            }

            ++linecount;
        }
        infile.close();
    }

    return true;
}
