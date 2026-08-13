///////////////////////////////////////////////////////////////////////////////
// trkparamsDriver.cpp
#include "TcPch.h"
#pragma hdrstop

#include "trkparamsDriver.h"
#include "trkparamsClassFactory.h"

DECLARE_GENERIC_DEVICE(TRKPARAMSDRV)

IOSTATUS CtrkparamsDriver::OnLoad( )
{
	TRACE(_T("CObjClassFactory::OnLoad()\n") );
	m_pObjClassFactory = new CtrkparamsClassFactory();

	return IOSTATUS_SUCCESS;
}

VOID CtrkparamsDriver::OnUnLoad( )
{
	delete m_pObjClassFactory;
}

unsigned long _cdecl CtrkparamsDriver::TRKPARAMSDRV_GetVersion( )
{
	return( (TRKPARAMSDRV_Major << 8) | TRKPARAMSDRV_Minor );
}

