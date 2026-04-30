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

        std::string kReplyString;

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

                if(ret == 0)
                {
                    kReplyString = "ok";
                }
                else
                {
                    kReplyString = "nok";
                }

                kReplyString += ";" + std::to_string(ret);
            }
            else if (command == "initcamera")
            {
                bool ret = M_initCamera();

                if(ret)
                {
                    kReplyString = "ok";
                }
                else
                {
                    kReplyString = "nok";
                }
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
                kReplyString = "ok";
            }
            else if (command == "halt")
            {
                M_halt_acquisition();
                kReplyString = "ok";
            }
            else if (command == "poweron")
            {
                M_powerOn();
                kReplyString = "ok";
            }
            else if (command == "poweroff")
            {
                M_powerOff();
                kReplyString = "ok";
            }
            else if (command == "getpower")
            {
                //TODO reply value
                M_getPower();
                kReplyString = "ok";
            }
            else if (command == "close")
            {
                M_close();
                kReplyString = "ok";
            }
        }
        catch (const std::exception& e)
        {
            kReplyString = std::string("nok;" + std::string(e.what()));
        }

        //  Send reply back to client
        zmq::message_t reply (kReplyString.length());
        memcpy (reply.data (), kReplyString.data(), kReplyString.length());
        socket.send (reply, zmq::send_flags::none);
    }
    return 0;
}