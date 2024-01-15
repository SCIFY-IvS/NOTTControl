///////////////////////////////////////////////////////////////////////////////
// trkmoduleDriver.cpp
#include "TcPch.h"
#pragma hdrstop

#include "trkmoduleDriver.h"
#include "trkmoduleClassFactory.h"

DECLARE_GENERIC_DEVICE(TRKMODULEDRV)

IOSTATUS CtrkmoduleDriver::OnLoad( )
{
	TRACE(_T("CObjClassFactory::OnLoad()\n") );
	m_pObjClassFactory = new CtrkmoduleClassFactory();

	return IOSTATUS_SUCCESS;
}

VOID CtrkmoduleDriver::OnUnLoad( )
{
	delete m_pObjClassFactory;
}

unsigned long _cdecl CtrkmoduleDriver::TRKMODULEDRV_GetVersion( )
{
	return( (TRKMODULEDRV_Major << 8) | TRKMODULEDRV_Minor );
}

