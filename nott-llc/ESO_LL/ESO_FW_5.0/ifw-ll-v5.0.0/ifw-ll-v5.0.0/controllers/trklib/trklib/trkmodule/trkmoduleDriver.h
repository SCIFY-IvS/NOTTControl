///////////////////////////////////////////////////////////////////////////////
// trkmoduleDriver.h

#ifndef __TRKMODULEDRIVER_H__
#define __TRKMODULEDRIVER_H__

#if _MSC_VER > 1000
#pragma once
#endif // _MSC_VER > 1000

#include "TcBase.h"

#define TRKMODULEDRV_NAME        "TRKMODULE"
#define TRKMODULEDRV_Major       1
#define TRKMODULEDRV_Minor       0

#define DEVICE_CLASS CtrkmoduleDriver

#include "ObjDriver.h"

class CtrkmoduleDriver : public CObjDriver
{
public:
	virtual IOSTATUS	OnLoad();
	virtual VOID		OnUnLoad();

	//////////////////////////////////////////////////////
	// VxD-Services exported by this driver
	static unsigned long	_cdecl TRKMODULEDRV_GetVersion();
	//////////////////////////////////////////////////////
	
};

Begin_VxD_Service_Table(TRKMODULEDRV)
	VxD_Service( TRKMODULEDRV_GetVersion )
End_VxD_Service_Table


#endif // ifndef __TRKMODULEDRIVER_H__