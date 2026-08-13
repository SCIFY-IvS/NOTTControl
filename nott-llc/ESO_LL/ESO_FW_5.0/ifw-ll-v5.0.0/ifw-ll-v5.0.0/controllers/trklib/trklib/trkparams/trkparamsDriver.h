///////////////////////////////////////////////////////////////////////////////
// trkparamsDriver.h

#ifndef __TRKPARAMSDRIVER_H__
#define __TRKPARAMSDRIVER_H__

#if _MSC_VER > 1000
#pragma once
#endif // _MSC_VER > 1000

#include "TcBase.h"

#define TRKPARAMSDRV_NAME        "TRKPARAMS"
#define TRKPARAMSDRV_Major       1
#define TRKPARAMSDRV_Minor       0

#define DEVICE_CLASS CtrkparamsDriver

#include "ObjDriver.h"

class CtrkparamsDriver : public CObjDriver
{
public:
	virtual IOSTATUS	OnLoad();
	virtual VOID		OnUnLoad();

	//////////////////////////////////////////////////////
	// VxD-Services exported by this driver
	static unsigned long	_cdecl TRKPARAMSDRV_GetVersion();
	//////////////////////////////////////////////////////
	
};

Begin_VxD_Service_Table(TRKPARAMSDRV)
	VxD_Service( TRKPARAMSDRV_GetVersion )
End_VxD_Service_Table


#endif // ifndef __TRKPARAMSDRIVER_H__