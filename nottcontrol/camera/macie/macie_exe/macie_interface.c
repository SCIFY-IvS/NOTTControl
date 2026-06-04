#include "macie_interface.h"
#include <stdio.h>
#include <string>
#include "macie_lib.h"
#include "MacieMain.h"
#include <iostream>
#include "macie.h"

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
extern "C" void M_acquire(const bool no_recon)
{
    std::cout << "Calling acquire" << std::endl;;
    std::cout << no_recon;
    acquire(no_recon, _ptUserData);
    return;
}

extern "C" void M_halt_acquisition()
{
    std::cout << "Calling halt" << std::endl;;
    halt_acquisition(_ptUserData);
    return;
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

extern "C" void M_powerOff()
{
    std::cout << "Calling powerOff" << std::endl;;
    SetPowerASIC(_ptUserData, false);
}
extern "C" void M_powerOn()
{
    std::cout << "Calling powerOn" << std::endl;;
    SetPowerASIC(_ptUserData, true);
}

extern "C" void M_getPower()
{
    std::cout << "Calling getPower" << std::endl;
    bool pArr[MACIE_PWR_CTRL_SIZE];
    GetPower(_ptUserData, pArr);
}

extern "C" void M_close()
{
    std::cout << "Calling close" << std::endl;
    SetPowerASIC(_ptUserData, false);
    free_resources(_ptUserData);
}

extern "C" bool M_exposure_settings(bool save, int ncoadds, int nseq, int ngroups, int nreads, int ndrops, int nresets)
{
    printf("Calling exposure_settings, save %d, ncoadds %d, nseq %d, ngroups %d, nreads %d, ndrops %d, nresets %d \n", save, ncoadds, nseq, ngroups, nreads, ndrops, nresets);
    return set_exposure_settings(_ptUserData, save, ncoadds, nseq,
                                      ngroups, nreads, ndrops, nresets);
}

extern "C" bool M_frame_settings(bool xWindowing, bool yWindowing, int x1, int x2, int y1, int y2)
{
    printf("Calling frame_settings, xWindowing %d, yWindowing %d, x1 %d, x2 %d, y1 %d, y2 %d\n", xWindowing, yWindowing, x1, x2, y1, y2);
    return set_frame_settings(_ptUserData, xWindowing, yWindowing, x1, x2, y1, y2);
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
                M_acquire(norecon);
                result = true; //TODO
            }
            else if (command == "halt")
            {
                M_halt_acquisition();
                result = true;
            }
            else if (command == "poweron")
            {
                M_powerOn();
                result = true;
            }
            else if (command == "poweroff")
            {
                M_powerOff();
                result = true;
            }
            else if (command == "getpower")
            {
                //TODO reply value
                M_getPower();
                result = true;
            }
            else if (command == "close")
            {
                M_close();
                result = true;
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

        //  Send reply back to client
        zmq::message_t reply (kReplyString.length());
        memcpy (reply.data (), kReplyString.data(), kReplyString.length());
        socket.send (reply, zmq::send_flags::none);
    }
    return 0;
}