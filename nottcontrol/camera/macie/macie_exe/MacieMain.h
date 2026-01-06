#include <string>
#include "macie.h"
#include "macie_lib.h"

int initialize(string configFile, MACIE_Settings *ptUserData);
void acquire(bool no_recon, MACIE_Settings *ptUserData);
bool InitCamera(string configFile, MACIE_Connection connection, MACIE_Settings *ptUserData);
bool free_resources(MACIE_Settings *ptUserData);
void toggle_offline_testing(bool offline_testing, MACIE_Settings *ptUserData);