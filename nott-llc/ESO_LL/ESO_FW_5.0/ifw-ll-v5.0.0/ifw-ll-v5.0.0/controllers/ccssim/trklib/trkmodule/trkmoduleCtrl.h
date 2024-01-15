///////////////////////////////////////////////////////////////////////////////
// trkmoduleCtrl.h

#ifndef __TRKMODULECTRL_H__
#define __TRKMODULECTRL_H__

#include <atlbase.h>
#include <atlcom.h>

#define TRKMODULEDRV_NAME "TRKMODULE"

#include "resource.h"       // main symbols
#include "trkmoduleW32.h"
#include "TcBase.h"
#include "trkmoduleClassFactory.h"
#include "TcOCFCtrlImpl.h"

class CtrkmoduleCtrl 
	: public CComObjectRootEx<CComMultiThreadModel>
	, public CComCoClass<CtrkmoduleCtrl, &CLSID_trkmoduleCtrl>
	, public ItrkmoduleCtrl
	, public ITcOCFCtrlImpl<CtrkmoduleCtrl, CtrkmoduleClassFactory>
{
public:
	CtrkmoduleCtrl();
	virtual ~CtrkmoduleCtrl();

DECLARE_REGISTRY_RESOURCEID(IDR_TRKMODULECTRL)
DECLARE_NOT_AGGREGATABLE(CtrkmoduleCtrl)

DECLARE_PROTECT_FINAL_CONSTRUCT()

BEGIN_COM_MAP(CtrkmoduleCtrl)
	COM_INTERFACE_ENTRY(ItrkmoduleCtrl)
	COM_INTERFACE_ENTRY(ITcCtrl)
	COM_INTERFACE_ENTRY(ITcCtrl2)
END_COM_MAP()

};

#endif // #ifndef __TRKMODULECTRL_H__
