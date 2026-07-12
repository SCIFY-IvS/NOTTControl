#include "macie_interface.h"
#include <stdio.h>
#include <string>
#include "macie_lib.h"
#include "MacieMain.h"
#include <iostream>
#include "macie.h"
#include <dirent.h>
#include <sys/stat.h>
#include <fstream>
#include <vector>

#include <zmq.hpp>

string _configFile = "";
MACIE_Settings *_ptUserData;

extern "C" int M_initialize(const char* configFile, bool offline_mode)
{
    string cfgFile = string(configFile);
    printf("Test before \n");
    printf("Calling initialize, configfile %s, offline_mode %d \n", configFile, offline_mode);
    printf("Test \n");
    _configFile = cfgFile;
    printf("Making MACIE_Settings... \n");
    _ptUserData = new MACIE_Settings;
    printf("Calling initialize... \n");
    int ret = initialize(cfgFile, _ptUserData);
    if(offline_mode)
    {
        toggle_offline_testing(true, _ptUserData);
    }
    return ret;
}
extern "C" bool M_acquire(const bool no_recon)
{
    std::cout << "Calling acquire" << std::endl;;
    std::cout << no_recon;
    return acquire(no_recon, _ptUserData);
}

extern "C" bool M_halt_acquisition()
{
    std::cout << "Calling halt" << std::endl;;
    return halt_acquisition(_ptUserData);
}

extern "C" bool M_initCamera()
{
    std::cout << "Calling initCamera" << std::endl;;
    if(_configFile.empty()){
        std::cout << "Init failed, config file not set" << std::endl;;
        return false;
    }
    return InitCamera(_configFile, MACIE_GigE, _ptUserData);
}

extern "C" bool M_powerOff()
{
    std::cout << "Calling powerOff" << std::endl;;
    return SetPowerASIC(_ptUserData, false);
}
extern "C" bool M_powerOn()
{
    std::cout << "Calling powerOn" << std::endl;;
    return SetPowerASIC(_ptUserData, true);
}

extern "C" bool M_getPower(bool *power)
{
    std::cout << "Calling getPower" << std::endl;

    return GetPowerASIC(_ptUserData, power);
}

extern "C" bool M_close()
{
    std::cout << "Calling close" << std::endl;
    bool ret1 = SetPowerASIC(_ptUserData, false);
    bool ret2 = free_resources(_ptUserData);
    return ret1 && ret2;
}

extern "C" bool M_exposure_settings(bool save, int ncoadds, int nseq, int ngroups, int nreads, int ndrops, int nresets)
{
    printf("Calling exposure_settings, save %d, ncoadds %d, nseq %d, ngroups %d, nreads %d, ndrops %d, nresets %d \n", save, ncoadds, nseq, ngroups, nreads, ndrops, nresets);
    return set_exposure_settings(_ptUserData, save, ncoadds, nseq,
                                      ngroups, nreads, ndrops, nresets);
}

extern "C" bool M_read_exposure_settings(bool &save, uint &ncoadds, uint &nseq, uint &ngroups, uint &nreads, uint &ndrops, uint &nresets)
{
    load_exposure_settings(_ptUserData, save, ncoadds, nseq, ngroups, nreads, ndrops, nresets);
    return true;
}

extern "C" bool M_set_integration_time(double tint_ms, int ngmax, int ncoadds, int nseq, bool save,
                                      double *actual_tint_ms, uint *ngroups, uint *ndrops, uint *nreads)
{
    if (_ptUserData == NULL)
        return false;

    unsigned int ng = 0;
    unsigned int nr = 0;
    unsigned int nd = 0;
    unsigned int nresets = ASIC_NResets(_ptUserData, false, 0);

    if (calc_ramp_settings(_ptUserData, tint_ms, ngmax, &ng, &nd, &nr) == false)
        return false;

    if (ncoadds < 1)
        ncoadds = 1;
    if (nseq < 1)
        nseq = 1;

    if (set_exposure_settings(_ptUserData, save, (uint)ncoadds, (uint)nseq, ng, nr, nd, nresets) == false)
        return false;

    if (actual_tint_ms != NULL)
        *actual_tint_ms = exposure_inttime_ms(_ptUserData);
    if (ngroups != NULL)
        *ngroups = ng;
    if (ndrops != NULL)
        *ndrops = nd;
    if (nreads != NULL)
        *nreads = nr;
    return true;
}

extern "C" bool M_read_integration_time(double *tint_ms)
{
    if (_ptUserData == NULL || tint_ms == NULL)
        return false;
    *tint_ms = exposure_inttime_ms(_ptUserData);
    return true;
}

extern "C" bool M_frame_settings(bool xWindowing, bool yWindowing, int x1, int x2, int y1, int y2)
{
    printf("Calling frame_settings, xWindowing %d, yWindowing %d, x1 %d, x2 %d, y1 %d, y2 %d\n", xWindowing, yWindowing, x1, x2, y1, y2);
    return set_frame_settings(_ptUserData, xWindowing, yWindowing, x1, x2, y1, y2);
}

extern "C" bool M_read_frame_settings(bool &xWindowing, bool &yWindowing, uint &x1, uint &x2, uint &y1, uint &y2)
{
    load_frame_settings(_ptUserData, xWindowing, yWindowing, x1, x2, y1, y2);
    return true;
}

extern "C" CAMERA_MODE M_get_detector_mode()
{
    return _ptUserData->DetectorMode;
}

//  Receive 0MQ string from socket and convert into string
inline static std::string
s_recv (zmq::socket_t & socket, zmq::recv_flags flags = zmq::recv_flags::none) {

    zmq::message_t message;
	zmq::recv_result_t rc = socket.recv(message, flags);
	if (rc) {
		return std::string(static_cast<char*>(message.data()), message.size());
	} else {
		return "";
	}

}

std::vector<std::string> split(std::string s, const std::string& delimiter) {
    std::vector<std::string> tokens;
    size_t pos = 0;
    std::string token;
    while ((pos = s.find(delimiter)) != std::string::npos) {
        token = s.substr(0, pos);
        tokens.push_back(token);
        s.erase(0, pos + delimiter.length());
    }
    tokens.push_back(s);

    return tokens;
}

static std::string newest_fits_in_save_dir(MACIE_Settings *ptUserData)
{
    if (ptUserData == NULL || ptUserData->saveDir.empty())
    {
        return "";
    }

    const std::string &strDir = ptUserData->saveDir;
    DIR *dir = opendir(strDir.c_str());
    if (dir == NULL)
    {
        return "";
    }

    struct dirent *ent;
    std::string newest_path;
    time_t newest_mtime = 0;
    while ((ent = readdir(dir)) != NULL)
    {
        std::string name = ent->d_name;
        if (name.size() < 6)
        {
            continue;
        }
        if (name.rfind(".fits") == std::string::npos &&
            name.rfind(".FITS") == std::string::npos)
        {
            continue;
        }

        std::string full = strDir + name;
        struct stat st;
        if (stat(full.c_str(), &st) != 0)
        {
            continue;
        }
        if (newest_path.empty() || st.st_mtime >= newest_mtime)
        {
            newest_mtime = st.st_mtime;
            newest_path = full;
        }
    }
    closedir(dir);
    return newest_path;
}

static bool read_binary_file(const std::string &path, std::string &out)
{
    std::ifstream file(path.c_str(), std::ios::binary);
    if (!file)
    {
        return false;
    }
    file.seekg(0, std::ios::end);
    std::streamsize size = file.tellg();
    if (size <= 0)
    {
        return false;
    }
    file.seekg(0, std::ios::beg);
    out.resize(static_cast<size_t>(size));
    if (!file.read(&out[0], size))
    {
        return false;
    }
    return true;
}


//Main zmq loop that handles requests
int main () {
    static const int kNumberOfThreads = 2;
    zmq::context_t context (kNumberOfThreads);
    zmq::socket_t socket (context, zmq::socket_type::rep);
    socket.bind ("tcp://*:65534");

    while (true) {
        //  Wait for next request from client
        std::string request = s_recv(socket);
        std::cout << "Received request " << request << std::endl;

        //Did the operation succeed?
        bool result;
        //What is the answer?
        std::string answer = "";
        bool send_binary = false;
        std::string binary_payload;

        try{
            auto tokens = split(request, ";");

            std::string command = tokens[0];
            std::cout << "Received command " << command << std::endl;

            

            if(command == "init")
            {
                std::string configFile = tokens[1];
                std::string offlineMode_str = tokens[2];
                bool offlineMode = false;
                if(offlineMode_str == "true")
                {
                    offlineMode = true;
                }

                int ret = M_initialize(configFile.c_str(), offlineMode);

                result = ret == 0;
                answer = std::to_string(ret);
            }
            else if (command == "initcamera")
            {
                result = M_initCamera();
            }
            else if (command == "acquire")
            {
                std::string norecon_str = tokens[1];
                bool norecon = false;
                if(norecon_str == "true")
                {
                    norecon = true;
                }
                result = M_acquire(norecon);
            }
            else if (command == "halt")
            {
                result = M_halt_acquisition();
            }
            else if (command == "poweron")
            {
                result = M_powerOn();
            }
            else if (command == "poweroff")
            {
                result = M_powerOff();
            }
            else if (command == "getpower")
            {
                bool power = false;
                result = M_getPower(&power);
                answer = (std::string) (power ? "true" : "false");
            }
            else if (command == "close")
            {
                result = M_close();
            }
            else if (command == "expsettings")
            {
                std::string save_str = tokens[1];
                bool save = save_str == "true";
                int ncoadds = std::stoi(tokens[2]);
                int nseq = std::stoi(tokens[3]);
                int ngroups = std::stoi(tokens[4]);
                int nreads = std::stoi(tokens[5]);
                int ndrops = std::stoi(tokens[6]);
                int nresets = std::stoi(tokens[7]);

                result = M_exposure_settings(save, ncoadds, nseq, ngroups, nreads, ndrops, nresets);          
            }
            else if (command == "rexpsettings")
            {
                bool save = false;
                uint ncoadds = 0;
                uint nseq = 0;
                uint ngroups = 0;
                uint nreads = 0;
                uint ndrops = 0;
                uint nresets = 0;
                result = M_read_exposure_settings(save, ncoadds, nseq, ngroups, nreads, ndrops, nresets);
                answer = (std::string) (save ? "true" : "false") + ";"
                    + std::to_string(ncoadds) + ";"
                    + std::to_string(nseq) + ";"
                    + std::to_string(ngroups) + ";"
                    + std::to_string(nreads) + ";"
                    + std::to_string(ndrops) + ";"
                    + std::to_string(nresets);
            }
            else if (command == "inttime")
            {
                double tint_ms = std::stod(tokens[1]);
                int ngmax = std::stoi(tokens[2]);
                int ncoadds = std::stoi(tokens[3]);
                int nseq = std::stoi(tokens[4]);
                bool save = tokens[5] == "true";
                double actual_tint_ms = 0.0;
                uint ngroups = 0;
                uint ndrops = 0;
                uint nreads = 0;
                result = M_set_integration_time(
                    tint_ms, ngmax, ncoadds, nseq, save,
                    &actual_tint_ms, &ngroups, &ndrops, &nreads);
                answer = std::to_string(actual_tint_ms) + ";"
                    + std::to_string(ngroups) + ";"
                    + std::to_string(ndrops) + ";"
                    + std::to_string(nreads);
            }
            else if (command == "readinttime")
            {
                double tint_ms = 0.0;
                result = M_read_integration_time(&tint_ms);
                answer = std::to_string(tint_ms);
            }
            else if (command == "framesettings")
            {
                bool xWindow = tokens[1] == "true";
                bool yWindow = tokens[2] == "true";
                int x1 = std::stoi(tokens[3]);
                int x2 = std::stoi(tokens[4]);
                int y1 = std::stoi(tokens[5]);
                int y2 = std::stoi(tokens[6]);

                result = M_frame_settings(xWindow, yWindow, x1, x2, y1, y2);
            }
            else if (command == "rframesettings")
            {
                bool xWindowing = false;
                bool yWindowing = false;
                uint x1 = 0;
                uint x2 = 0;
                uint y1 = 0;
                uint y2 = 0;
                result = M_read_frame_settings(xWindowing, yWindowing, x1, x2, y1, y2);
                answer = (std::string) (xWindowing ? "true" : "false") + ";"
                    + (yWindowing ? "true" : "false") + ";"
                    + std::to_string(x1) + ";"
                    + std::to_string(x2) + ";"
                    + std::to_string(y1) + ";"
                    + std::to_string(y2);
            }
            else if (command == "getmode")
            {
                result = true;
                CAMERA_MODE mode = M_get_detector_mode();
                if(mode == CAMERA_MODE::CAMERA_MODE_SLOW)
                {
                    answer = "slow";
                }
                else if (mode == CAMERA_MODE::CAMERA_MODE_FAST)
                {
                    answer = "fast";
                }
            }
            else if (command == "getsavedir")
            {
                result = _ptUserData != NULL;
                answer = result ? _ptUserData->saveDir : "";
            }
            else if (command == "newestfits")
            {
                answer = newest_fits_in_save_dir(_ptUserData);
                result = !answer.empty();
            }
            else if (command == "fetchnewestfits")
            {
                std::string fits_path = newest_fits_in_save_dir(_ptUserData);
                result = !fits_path.empty() &&
                         read_binary_file(fits_path, binary_payload);
                if (result)
                {
                    size_t pos = fits_path.find_last_of("/\\");
                    answer = pos == std::string::npos
                        ? fits_path
                        : fits_path.substr(pos + 1);
                    send_binary = true;
                }
                else
                {
                    answer = "no fits file found on server";
                }
            }
            else 
            {
                result = false;
                answer = "unknown command";
            }
        }
        catch (const std::exception& e)
        {
            result = false;
            answer = std::string(e.what());
        }

        std::string resultString = result ? "ok" : "nok";
        std::string kReplyString = resultString + ";" + answer;

        std::cout << "Sending answer " << kReplyString << std::endl;

        //  Send reply back to client
        zmq::message_t reply (kReplyString.length());
        memcpy (reply.data (), kReplyString.data(), kReplyString.length());
        if (send_binary)
        {
            zmq::message_t blob(binary_payload.size());
            memcpy(blob.data(), binary_payload.data(), binary_payload.size());
            socket.send(reply, zmq::send_flags::sndmore);
            socket.send(blob, zmq::send_flags::none);
        }
        else
        {
            socket.send (reply, zmq::send_flags::none);
        }
    }
    return 0;
}