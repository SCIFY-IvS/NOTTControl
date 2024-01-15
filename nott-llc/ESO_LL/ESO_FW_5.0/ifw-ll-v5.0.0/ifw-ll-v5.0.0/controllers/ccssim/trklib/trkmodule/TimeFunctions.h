#pragma once
#include "TcServices.h"


#define OFFSET_UNIX 946684800  // seconds between years 1970 and 2000 
#define TIME_AHEAD  50000      // time (usec) ahead for computation of parameters 

/*
 * Local definitions
 */
#define CONST1 1721013.5      /* constant used in formula */
#define CONST2 190002.5       /* constant used in formula */
#define CONST3 2400000.5      /* constant used in formula */
#define CONST4 2440587.5      /* JD for 1970-01-01 00:00:00.000000 */

enum class TimeMode
{
	LOCAL,
	UTC_PTP,
	UTC_NTP,
	SIMULATION
};

typedef struct {
	LONGLONG tv_sec;
	LONGLONG tv_usec;
	double   usec;
} ccsTIMEVAL;

extern DOUBLE  timeUTCToJD(ccsTIMEVAL *ut);
extern DOUBLE  timeUTCToMJD(ccsTIMEVAL *ut);
extern HRESULT timeGetUTC(LONGLONG dcTime, ccsTIMEVAL *ccsUTC);
extern HRESULT timeGetUTCInFuture(LONGLONG dcTime, ccsTIMEVAL *ccsUTC, LONGLONG time_ahead);
extern HRESULT timeGetDcTime(ccsTIMEVAL vltUTC, LONGLONG *dcTime);
extern HRESULT timeGetAbsoluteDcTime(LONGLONG timeDiff, LONGLONG *dcTime);
extern double timeGetMudpiTime(LONGLONG dcTime, LONG leap_second);
extern double timeGetMudpiTimeInFuture(LONGLONG dcTime, LONG leap_second, double time_ahead);

