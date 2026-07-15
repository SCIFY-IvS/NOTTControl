///////////////////////////////////////////////////////////////////////////////
// trkparamsCtrl.h

#ifndef __TRKPARAMSCTRL_H__
#define __TRKPARAMSCTRL_H__

#include <atlbase.h>
#include <atlcom.h>

#define TRKPARAMSDRV_NAME "TRKPARAMS"

#include "resource.h"       // main symbols
#include "trkparamsW32.h"
#include "TcBase.h"
#include "trkparamsClassFactory.h"
#include "TcOCFCtrlImpl.h"

class CtrkparamsCtrl 
	: public CComObjectRootEx<CComMultiThreadModel>
	, public CComCoClass<CtrkparamsCtrl, &CLSID_trkparamsCtrl>
	, public ItrkparamsCtrl
	, public ITcOCFCtrlImpl<CtrkparamsCtrl, CtrkparamsClassFactory>
{
public:
	CtrkparamsCtrl();
	virtual ~CtrkparamsCtrl();

DECLARE_REGISTRY_RESOURCEID(IDR_TRKPARAMSCTRL)
DECLARE_NOT_AGGREGATABLE(CtrkparamsCtrl)

DECLARE_PROTECT_FINAL_CONSTRUCT()

BEGIN_COM_MAP(CtrkparamsCtrl)
	COM_INTERFACE_ENTRY(ItrkparamsCtrl)
	COM_INTERFACE_ENTRY(ITcCtrl)
	COM_INTERFACE_ENTRY(ITcCtrl2)
END_COM_MAP()

};

#endif // #ifndef __TRKPARAMSCTRL_H__
